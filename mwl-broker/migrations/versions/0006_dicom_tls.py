"""add DICOM TLS flags to sources and targets

Revision ID: 0006_dicom_tls
Revises: 0005_local_worklist
Create Date: 2026-09-17

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_dicom_tls"
down_revision = "0005_local_worklist"
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
    for table in ("mwl_source", "pacs_target"):
        _add_column(inspector, table, "tls", sa.Boolean(), server_default=sa.false())
        _add_column(inspector, table, "tls_verify", sa.Boolean(), server_default=sa.true())


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ("mwl_source", "pacs_target"):
        if table in inspector.get_table_names():
            columns = {col["name"] for col in inspector.get_columns(table)}
            for column in ("tls_verify", "tls"):
                if column in columns:
                    op.drop_column(table, column)
