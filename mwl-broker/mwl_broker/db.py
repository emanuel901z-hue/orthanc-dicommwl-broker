"""DB engine/session factory — lazy so tests can override DATABASE_URL
via BROKER_DATABASE_URL before first use."""
import logging
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
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
# The base schema comes from the models (`create_all`). Ordered migrations for
# *existing* installations live in `migrations/` (Alembic); every revision after
# the baseline is defensive, because a fresh database already carries the
# current schema when it runs. See migrations/versions/0001_baseline.py.
BASELINE_REVISION = "0001_baseline"
_PROJECT_DIR = Path(__file__).resolve().parent.parent
_MIGRATIONS_DIR = _PROJECT_DIR / "migrations"


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(_PROJECT_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    return cfg


def upgrade_schema(engine=None) -> None:
    """Bring the database to the latest revision (idempotent, defensive).

    A database that predates Alembic has no version table: its base schema is
    already in place, so the baseline is *stamped* and only the later revisions
    run.
    """
    from alembic import command
    from alembic.runtime.migration import MigrationContext

    engine = engine or get_engine()
    cfg = _alembic_config()
    with engine.begin() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
        cfg.attributes["connection"] = conn
        if current is None and inspect(conn).has_table("mwl_source"):
            log.info("migration: stamping baseline %s on an existing database",
                     BASELINE_REVISION)
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")


def init_db() -> None:
    """Create missing tables, then migrate an existing schema to head."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    upgrade_schema(engine)


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
