"""add HL7 to DICOM field mappings

Revision ID: 0010_hl7_field_map
Revises: 0009_merge_rules
Create Date: 2026-09-21

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_hl7_field_map"
down_revision = "0009_merge_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "hl7_field_map" in inspector.get_table_names():
        return
    op.create_table(
        "hl7_field_map",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("segment", sa.String(8), nullable=False, server_default=""),
        sa.Column("field", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("component", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_tag", sa.String(64), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("hl7_field_map")
