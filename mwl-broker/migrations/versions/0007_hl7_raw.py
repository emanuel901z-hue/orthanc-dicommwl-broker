"""add an optional raw HL7 message column (off by default, PHI!)

Revision ID: 0007_hl7_raw
Revises: 0006_dicom_tls
Create Date: 2026-09-21

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_hl7_raw"
down_revision = "0006_dicom_tls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    table = "hl7_message"
    if table not in inspector.get_table_names():
        return
    if "raw" in {col["name"] for col in inspector.get_columns(table)}:
        return
    op.add_column(table, sa.Column("raw", sa.Text(), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("hl7_message", "raw")
