"""Schema initialisation and the Alembic migration path."""
import pytest
from sqlalchemy import inspect, text

from mwl_broker import db
from mwl_broker.models import Base

# Columns that existed in the first release. Everything a model has beyond this
# needs a migration, otherwise an *existing* production database is missing it
# (create_all never alters existing tables) and the API starts failing.
BASELINE_COLUMNS = {
    "query_log": {
        "id", "ts", "calling_aet", "query_keys", "answers", "per_source",
        "duration_ms", "status",
    },
    "mwl_source": {
        "id", "name", "aet", "host", "port", "calling_aet", "charset",
        "enabled", "timeout_s", "priority", "created_at",
    },
    "store_log": {
        "id", "ts", "calling_aet", "sop_instance_uid", "study_uid", "accession",
        "source_id", "target_id", "status", "error",
    },
}


def _columns(engine, table: str) -> set[str]:
    return {col["name"] for col in inspect(engine).get_columns(table)}


def _model_columns(table: str) -> set[str]:
    return {col.name for col in Base.metadata.tables[table].columns}


def test_migrations_restore_everything_the_models_need():
    """The bug class that bit us on Postgres: a new column without a migration.

    Simulate an installation from before Alembic (no version table, only the
    baseline columns), then migrate — every column must be back.
    """
    engine = db.get_engine()
    dropped = 0
    with engine.begin() as conn:
        # an installation from before Alembic existed: no version table ...
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        # ... and only the baseline columns
        for table, baseline in BASELINE_COLUMNS.items():
            for extra in sorted(_columns(engine, table) - baseline):
                conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {extra}"))
                dropped += 1
    assert dropped > 0, "nothing to drop — is the baseline list up to date?"

    db.upgrade_schema(engine)

    for table, baseline in BASELINE_COLUMNS.items():
        assert _columns(engine, table) == _model_columns(table), (
            f"{table}: migrations did not restore the model schema"
        )


def test_init_db_recreates_a_missing_table():
    """A dropped table comes back from create_all (migrations run only once)."""
    engine = db.get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE store_spool"))

    db.init_db()

    assert "store_spool" in inspect(engine).get_table_names()
    assert _columns(engine, "store_spool") == _model_columns("store_spool")


def test_fresh_database_gets_the_spool_table_from_migrations():
    """On a brand-new database (no create_all) revision 0003 builds the table."""
    from sqlalchemy import create_engine

    fresh = create_engine("sqlite://")
    with fresh.begin() as conn:
        # only the baseline schema exists — the spool table must come from 0003
        Base.metadata.create_all(conn)
        conn.execute(text("DROP TABLE store_spool"))

    db.upgrade_schema(fresh)

    assert "store_spool" in inspect(fresh).get_table_names()
    assert _columns(fresh, "store_spool") == _model_columns("store_spool")


def test_upgrade_is_idempotent():
    engine = db.get_engine()
    db.upgrade_schema(engine)
    db.upgrade_schema(engine)

    assert _columns(engine, "store_spool") == _model_columns("store_spool")


def test_init_db_creates_a_fresh_database():
    from mwl_broker.models import Base as Models

    engine = db.get_engine()
    db.init_db()

    tables = set(inspect(engine).get_table_names())
    assert set(Models.metadata.tables) <= tables
    # the version table exists and points at head
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() is not None


def test_alembic_stamp_marks_an_existing_database(monkeypatch):
    """A database without a version table gets the baseline stamped, not run."""
    from alembic.runtime.migration import MigrationContext

    engine = db.get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

    db.upgrade_schema(engine)

    with engine.connect() as conn:
        revision = MigrationContext.configure(conn).get_current_revision()
    assert revision is not None and revision != db.BASELINE_REVISION


def test_spool_directory_setting_is_validated():
    from mwl_broker import settings_service

    assert settings_service.validate_value("spool_dir", "/var/lib/mwl-broker/spool") == []
    assert settings_service.validate_value("spool_dir", "relative") == ["must be an absolute path"]
    assert settings_service.validate_value("spool_dir", "/a/../b") == ["must not contain '..'"]


@pytest.mark.parametrize("key,value", [
    ("spool_max_items", "0"),
    ("spool_max_attempts", "0"),
    ("spool_backoff_s", "1"),
    ("spool_poll_s", "0"),
])
def test_spool_settings_ranges(key, value):
    from mwl_broker import settings_service

    assert settings_service.validate_value(key, value), f"{key}={value} should be rejected"
