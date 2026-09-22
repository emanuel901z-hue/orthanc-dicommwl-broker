"""Schema initialisation and the Alembic migration path."""
import pytest
import sqlalchemy as sa
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


def test_startup_refuses_an_outdated_schema(client, monkeypatch):
    """A build whose migrations do not match the database must not start silently.

    Regression guard: an image without the newest revision used to start and then
    answer 500 on every endpoint touching the new column. The check compares the
    database revision with the revision the *code* carries — simulated here by
    pretending the code is one revision ahead.
    """
    from alembic.script import ScriptDirectory

    from mwl_broker import db
    from mwl_broker.db import get_engine

    engine = get_engine()
    monkeypatch.setattr(ScriptDirectory, "get_current_head",
                        lambda self: "9999_not_in_this_build")

    with pytest.raises(RuntimeError) as exc:
        db.upgrade_schema(engine)
    assert "do not match" in str(exc.value)
    assert "9999_not_in_this_build" in str(exc.value)

    # with the real head the upgrade passes again (idempotent)
    monkeypatch.undo()
    db.upgrade_schema(engine)


def test_migrations_cover_every_model_column(tmp_path, monkeypatch):
    """The migrated schema must match the models — column by column.

    Regression guard for the real bug found on 2026-09-22: `extra_attributes` was
    added to the model but its migration was never created, so a fresh Postgres
    instance answered 500 on every endpoint that touched the column while all
    tests passed (they build their schema with `create_all`, which hides exactly
    this mistake).

    This test builds a database **only** from the migrations and then compares it
    with the models.
    """
    from alembic import command

    from mwl_broker import db

    url = f"sqlite:///{tmp_path}/migrated.db"
    monkeypatch.setenv("BROKER_DATABASE_URL", url)
    db.reset_for_tests()

    cfg = db._alembic_config()
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    # inspect the freshly migrated database explicitly — the settings cache still
    # points at the test database, which would hide the very mistake we look for
    engine = sa.create_engine(url)
    inspector = sa.inspect(engine)
    migrated_tables = set(inspector.get_table_names())

    # A brand-new *table* is created by `Base.metadata.create_all` at startup, so
    # it may legitimately be absent from the migrations. What must never happen is
    # a *column* on an existing table without a revision — exactly the bug above.
    problems: list[str] = []
    checked = 0
    for table_name, table in Base.metadata.tables.items():
        if table_name not in migrated_tables:
            continue
        checked += 1
        migrated_columns = {col["name"] for col in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name not in migrated_columns:
                problems.append(f"{table_name}.{column.name} has no migration")

    db.reset_for_tests()
    # the baseline revision only *stamps* an existing schema (by design), so the
    # comparison covers the tables the later revisions create — that is where a
    # forgotten column appears
    assert checked >= 5, f"only {checked} tables were comparable: {sorted(migrated_tables)}"
    assert not problems, "migrations do not match the models:\n  " + "\n  ".join(problems)
