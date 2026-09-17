"""Alembic environment — uses the broker's settings and models."""
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# make `mwl_broker` importable when Alembic runs from the project directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mwl_broker.config import get_settings  # noqa: E402
from mwl_broker.models import Base  # noqa: E402

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    """An explicitly configured URL (tests/CLI) wins over the deployment settings."""
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # `db.init_db()` hands in an open connection so the bootstrap and the
    # upgrade share one transaction.
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _url()
    engine = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
