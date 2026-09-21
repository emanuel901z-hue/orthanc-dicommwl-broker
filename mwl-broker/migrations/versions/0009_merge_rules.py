"""add field-level merge rules

Revision ID: 0009_merge_rules
Revises: 0008_mpps
Create Date: 2026-09-21

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_merge_rules"
down_revision = "0008_mpps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "merge_rule" in inspector.get_table_names():
        return
    op.create_table(
        "merge_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tag", sa.String(64), nullable=False),
        sa.Column("sources", sa.String(512), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_merge_rule_tag", "merge_rule", ["tag"], unique=True)


def downgrade() -> None:
    op.drop_table("merge_rule")
