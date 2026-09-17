"""add per-station worklist rules

Revision ID: 0004_station_rules
Revises: 0003_store_spool
Create Date: 2026-09-17

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_station_rules"
down_revision = "0003_store_spool"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "station_rule" in inspector.get_table_names():
        return
    op.create_table(
        "station_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("station_aet", sa.String(16), nullable=False, server_default="*"),
        sa.Column("mode", sa.String(8), nullable=False, server_default="deny"),
        sa.Column("source_ids", sa.JSON(), nullable=True),
        sa.Column("source_priority", sa.JSON(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_station_rule_name", "station_rule", ["name"], unique=True)
    op.create_index("ix_station_rule_station_aet", "station_rule", ["station_aet"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "station_rule" in inspector.get_table_names():
        op.drop_table("station_rule")
