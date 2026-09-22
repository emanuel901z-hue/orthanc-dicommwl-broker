"""add the patient identifier merge table (IHE PIR)

Revision ID: 0012_patient_merge
Revises: 0011_local_extra
Create Date: 2026-09-22

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_patient_merge"
down_revision = "0011_local_extra"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "patient_merge" in inspector.get_table_names():
        return
    op.create_table(
        "patient_merge",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("old_patient_id", sa.String(64), nullable=False),
        sa.Column("new_patient_id", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(256), nullable=False, server_default=""),
        sa.Column("actor", sa.String(64), nullable=False, server_default="api"),
        sa.Column("origin", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_patient_merge_old", "patient_merge", ["old_patient_id"])
    op.create_index("ix_patient_merge_new", "patient_merge", ["new_patient_id"])
    op.create_index("ix_patient_merge_ts", "patient_merge", ["ts"])
    op.create_index("ix_patient_merge_active", "patient_merge", ["active"])


def downgrade() -> None:
    op.drop_table("patient_merge")
