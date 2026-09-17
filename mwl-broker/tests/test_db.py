"""Schema initialisation and the additive column migrations."""


# Columns that existed in the first release. Anything beyond this needs an
# entry in `_COLUMN_MIGRATIONS`, otherwise an existing production database
# (Postgres) is missing it and the API starts failing with 500s.
BASELINE_COLUMNS = {
    "query_log": {
        "id", "ts", "calling_aet", "query_keys", "answers", "per_source",
        "duration_ms", "status",
    },
    "mwl_source": {
        "id", "name", "aet", "host", "port", "calling_aet", "charset",
        "enabled", "timeout_s", "priority", "created_at",
    },
}


def test_every_late_column_has_a_migration():
    """Guard against the bug class: a new model column without an ALTER."""
    from sqlalchemy import inspect

    from mwl_broker import db

    inspector = inspect(db.get_engine())
    for table, baseline in BASELINE_COLUMNS.items():
        actual = {col["name"] for col in inspector.get_columns(table)}
        migrated = {col for tbl, col, _ddl in db._COLUMN_MIGRATIONS if tbl == table}
        missing = (actual - baseline) - migrated
        assert not missing, f"{table}: no migration for {sorted(missing)}"


def test_migrations_restore_dropped_columns():
    """Dropping the late columns and re-initialising must bring them back."""
    from sqlalchemy import inspect, text

    from mwl_broker import db

    engine = db.get_engine()
    with engine.begin() as conn:
        for table, column, _ddl in db._COLUMN_MIGRATIONS:
            conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))

    db.init_db()

    inspector = inspect(engine)
    for table, column, _ddl in db._COLUMN_MIGRATIONS:
        assert column in {col["name"] for col in inspector.get_columns(table)}


def test_migrations_are_idempotent():
    from mwl_broker import db

    db.init_db()
    db.init_db()
