"""DB engine/session factory — lazy so tests can override DATABASE_URL
via BROKER_DATABASE_URL before first use."""
import logging
import os
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
        # A hospital stack runs several background workers (echo loop, spool,
        # retention, ATNA, MPPS forwarding) next to the DIMSE handlers and the
        # API. The default pool (5 + 10 overflow) runs out under load and then
        # answers 500 on a plain read — size it explicitly.
        pool_args: dict = {"pool_pre_ping": True}
        if ":memory:" not in url:
            pool_args.update(
                pool_size=int(os.getenv("BROKER_DB_POOL_SIZE", "10")),
                max_overflow=int(os.getenv("BROKER_DB_MAX_OVERFLOW", "20")),
                pool_timeout=int(os.getenv("BROKER_DB_POOL_TIMEOUT", "15")),
                pool_recycle=1800,
            )
        if url.startswith("sqlite"):
            # The test suite runs on a file-based SQLite. Several tests use
            # threads (spool claims, cache snapshots) and the CI machine may be
            # busy — the 5 s default busy timeout then turns a *waiting* writer
            # into "database is locked" and a flaky failure. Waiting longer is
            # what a serialising database wants; Postgres is unaffected.
            pool_args["connect_args"] = {"timeout": 30}
        _engine = create_engine(url, **pool_args)
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


def upsert(session: Session, model, values, index_elements, *,
           update_columns: list | None = None, update_values: dict | None = None,
           returning: list | None = None):
    """`INSERT … ON CONFLICT DO UPDATE` — the same statement on Postgres and SQLite.

    Two DIMSE threads can create the same row at the same instant: a source's
    breaker state, a source's cache item. A plain insert loses that race with an
    IntegrityError, and inside the C-FIND handler that exception was answered to
    the modality as a DIMSE failure (`0xC311`) — a worklist query the broker could
    have served. Found by the load test, see `docs/loadtest.md`.

    `values` is one row dict or a list of them. Either name the columns whose new
    value should win (`update_columns` → `excluded.<column>`), or pass explicit
    `update_values` (which may be SQL expressions, e.g. `Model.failures + 1`).
    Without either, a conflict does nothing.
    """
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:  # pragma: no cover - MySQL/Oracle are not supported deployments
        raise RuntimeError(
            f"upsert() needs ON CONFLICT support, which {dialect!r} does not offer"
        )

    stmt = dialect_insert(model).values(values)
    if update_columns:
        stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_={column: stmt.excluded[column] for column in update_columns},
        )
    elif update_values is not None:
        stmt = stmt.on_conflict_do_update(index_elements=index_elements,
                                          set_=update_values)
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=index_elements)
    if returning:
        stmt = stmt.returning(*returning)
    return session.execute(stmt)


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

    # Fail fast when the image and its migrations do not match.
    #
    # Without this check the app starts happily on an old schema and then answers
    # 500 on every endpoint that touches the new column — a hospital notices that
    # at the modality, hours later. Better to refuse to start with a clear line.
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(cfg).get_current_head()
    with engine.connect() as conn:
        at = MigrationContext.configure(conn).get_current_revision()
    if at != head:
        raise RuntimeError(
            f"database schema is at revision {at or 'unknown'}, but this build needs "
            f"{head} — the container image and its migrations do not match. "
            "Rebuild the image (./build.sh mwl-broker) or restore a matching database.",
        )


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
