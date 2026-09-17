"""add the worklist-cache columns

Revision ID: 0002_cache_columns
Revises: 0001_baseline
Create Date: 2026-09-17

Replaces the hand-rolled `_COLUMN_MIGRATIONS` list. Defensive by design: on a
fresh database `create_all` has already added these columns, so each step
checks for its existence first.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_cache_columns"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def _add_column(inspector, table: str, column: str, type_, **kwargs) -> None:
    if table not in inspector.get_table_names():
        return
    if column in {col["name"] for col in inspector.get_columns(table)}:
        return
    op.add_column(table, sa.Column(column, type_, **kwargs))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # worklist cache (sprint 3)
    _add_column(inspector, "query_log", "served_stale", sa.JSON())
    _add_column(inspector, "mwl_source", "cache_stale_on_error", sa.Boolean(),
                server_default=sa.true())
    _add_column(inspector, "mwl_source", "cache_refresh_s", sa.Integer(),
                server_default="0")
    # earlier release (kept here so every installation converges)
    _add_column(inspector, "store_log", "applied_transforms", sa.JSON())


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table, column in (
        ("query_log", "served_stale"),
        ("mwl_source", "cache_stale_on_error"),
        ("mwl_source", "cache_refresh_s"),
        ("store_log", "applied_transforms"),
    ):
        if table in inspector.get_table_names():
            if column in {col["name"] for col in inspector.get_columns(table)}:
                op.drop_column(table, column)
