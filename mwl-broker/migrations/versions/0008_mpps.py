"""add the MPPS step table

Revision ID: 0008_mpps
Revises: 0007_hl7_raw
Create Date: 2026-09-21

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_mpps"
down_revision = "0007_hl7_raw"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "mpps_step" in inspector.get_table_names():
        return
    op.create_table(
        "mpps_step",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sop_instance_uid", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="IN PROGRESS"),
        sa.Column("accession", sa.String(64), nullable=False, server_default=""),
        sa.Column("patient_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("sps_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("station_aet", sa.String(16), nullable=False, server_default=""),
        sa.Column("modality", sa.String(16), nullable=False, server_default=""),
        sa.Column("study_uid", sa.String(128), nullable=False, server_default=""),
        sa.Column("performed_procedure_step_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("forwarded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("forward_error", sa.String(256), nullable=False, server_default=""),
        sa.Column("forward_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forwarded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mpps_step_sop_instance_uid", "mpps_step", ["sop_instance_uid"], unique=True)
    op.create_index("ix_mpps_step_ts", "mpps_step", ["ts"])
    op.create_index("ix_mpps_step_status", "mpps_step", ["status"])
    op.create_index("ix_mpps_step_forwarded", "mpps_step", ["forwarded"])


def downgrade() -> None:
    op.drop_table("mpps_step")
