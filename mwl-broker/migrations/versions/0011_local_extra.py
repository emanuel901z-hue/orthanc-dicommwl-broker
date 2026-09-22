"""add extra attributes to local worklist items (HL7 field mappings)

Revision ID: 0011_local_extra
Revises: 0010_hl7_field_map
Create Date: 2026-09-22

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_local_extra"
down_revision = "0010_hl7_field_map"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    table = "local_worklist_item"
    if table not in inspector.get_table_names():
        return
    if "extra_attributes" in {col["name"] for col in inspector.get_columns(table)}:
        return
    op.add_column(table, sa.Column("extra_attributes", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("local_worklist_item", "extra_attributes")
