"""DB engine/session factory — lazy so tests can override DATABASE_URL
via BROKER_DATABASE_URL before first use."""
import logging

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base, MwlSource, PacsTarget, RoutingRule

log = logging.getLogger("mwl_broker.db")

_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        _engine = create_engine(url, pool_pre_ping=True)
        if url.startswith("sqlite"):
            # SQLite disables FK enforcement by default; production runs on
            # Postgres, so tests must fail the same way when a delete would
            # violate a foreign key.
            from sqlalchemy import event

            @event.listens_for(_engine, "connect")
            def _enable_sqlite_fks(dbapi_conn, _record):  # pragma: no cover
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

    return _engine


def session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


def get_session() -> Session:
    return session_factory()()


# Idempotent column additions — this project intentionally has no Alembic;
# new columns on existing tables are added here. `create_all` only creates
# missing *tables*, never alters existing ones.
_COLUMN_MIGRATIONS: list[tuple[str, str, str]] = [
    ("store_log", "applied_transforms", "JSON"),
]


def _apply_column_migrations(engine) -> None:
    for table, column, ddl_type in _COLUMN_MIGRATIONS:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
            log.info("migration: added %s.%s", table, column)
        except Exception:
            pass  # column already exists (fresh DB or previously migrated)


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    _apply_column_migrations(engine)


def reset_for_tests() -> None:
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def seed_from_json(payload: list[dict]) -> None:
    """Idempotent upsert of sources/targets/rules from a JSON seed list.

    Items: {"kind": "source"|"target", ...model fields...}
    Rules:  {"kind": "rule", "source": "<name>", "target": "<name>", ...}
    Transforms: {"kind": "transform", "name": ..., "operations": [...],
                 "source": "<name>"?, "target": "<name>"?}
    Settings:   {"kind": "setting", "key": ..., "value": ...}
    """
    kind_model = {"source": MwlSource, "target": PacsTarget}
    with get_session() as s:
        for item in payload:
            item = dict(item)
            kind = item.pop("kind", "")
            if kind == "rule":
                _seed_rule(s, item)
                continue
            if kind == "transform":
                _seed_transform(s, item)
                continue
            if kind == "setting":
                _seed_setting(s, item)
                continue
            model = kind_model.get(kind)
            if model is None:
                continue
            existing = s.scalar(select(model).where(model.name == item["name"]))
            if existing is None:
                s.add(model(**item))
            else:
                for k, v in item.items():
                    setattr(existing, k, v)
        s.commit()


def _seed_transform(s, item: dict) -> None:
    """Upsert a transform rule; optional source/target referenced by name."""
    from .models import TransformRule

    def _id_by_name(model, name):
        if not name:
            return None
        row = s.scalar(select(model).where(model.name == name))
        if row is None:
            log.warning("seed transform: unknown %s %r", model.__name__, name)
        return row.id if row else None

    fields = {
        "enabled": item.get("enabled", True),
        "priority": item.get("priority", 100),
        "operations": item.get("operations", []),
        "source_id": _id_by_name(MwlSource, item.get("source")),
        "target_id": _id_by_name(PacsTarget, item.get("target")),
    }
    existing = s.scalar(select(TransformRule).where(TransformRule.name == item["name"]))
    if existing is None:
        s.add(TransformRule(name=item["name"], **fields))
    else:
        for k, v in fields.items():
            setattr(existing, k, v)


def _seed_setting(s, item: dict) -> None:
    """Upsert a runtime setting (validated against the known keys)."""
    from .settings_service import set_value, validate_value

    key = item.get("key", "")
    value = str(item.get("value", ""))
    errors = validate_value(key, value)
    if errors:
        log.warning("seed setting %r skipped: %s", key, "; ".join(errors))
        return
    set_value(key, value, session=s)


def _seed_rule(s, item: dict) -> None:
    """Upsert a routing rule referenced by source/target *names*."""
    src = s.scalar(select(MwlSource).where(MwlSource.name == item["source"]))
    tgt = s.scalar(select(PacsTarget).where(PacsTarget.name == item["target"]))
    if src is None or tgt is None:
        log.warning("seed rule skipped: unknown source/target %s", item)
        return
    fields = {"priority": item.get("priority", 100),
              "enabled": item.get("enabled", True)}
    existing = s.scalar(
        select(RoutingRule).where(
            RoutingRule.source_id == src.id, RoutingRule.target_id == tgt.id
        )
    )
    if existing is None:
        s.add(RoutingRule(source_id=src.id, target_id=tgt.id, **fields))
    else:
        for k, v in fields.items():
            setattr(existing, k, v)


def check_db() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
