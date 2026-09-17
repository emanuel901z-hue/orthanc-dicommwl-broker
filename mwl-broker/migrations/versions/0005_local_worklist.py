"""add local worklist items and the HL7 message log

Revision ID: 0005_local_worklist
Revises: 0004_station_rules
Create Date: 2026-09-17

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_local_worklist"
down_revision = "0004_station_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()

    if "local_worklist_item" not in tables:
        op.create_table(
            "local_worklist_item",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("accession", sa.String(64), nullable=False),
            sa.Column("sps_id", sa.String(64), nullable=False, server_default="1"),
            sa.Column("patient_id", sa.String(64), nullable=False, server_default=""),
            sa.Column("patient_name", sa.String(128), nullable=False, server_default=""),
            sa.Column("birth_date", sa.String(16), nullable=False, server_default=""),
            sa.Column("sex", sa.String(4), nullable=False, server_default=""),
            sa.Column("modality", sa.String(16), nullable=False, server_default=""),
            sa.Column("station_aet", sa.String(16), nullable=False, server_default=""),
            sa.Column("procedure_description", sa.String(128), nullable=False, server_default=""),
            sa.Column("scheduled_date", sa.String(16), nullable=False, server_default=""),
            sa.Column("scheduled_time", sa.String(16), nullable=False, server_default=""),
            sa.Column("study_uid", sa.String(128), nullable=False, server_default=""),
            sa.Column("sps_status", sa.String(16), nullable=False, server_default="SCHEDULED"),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("origin", sa.String(16), nullable=False, server_default="manual"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("accession", "sps_id", name="uq_local_item_step"),
        )
        op.create_index("ix_local_worklist_item_accession", "local_worklist_item", ["accession"])
        op.create_index("ix_local_worklist_item_valid_until", "local_worklist_item", ["valid_until"])

    if "hl7_message" not in tables:
        op.create_table(
            "hl7_message",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("transport", sa.String(8), nullable=False, server_default="http"),
            sa.Column("message_type", sa.String(16), nullable=False, server_default=""),
            sa.Column("control_id", sa.String(64), nullable=False, server_default=""),
            sa.Column("order_control", sa.String(8), nullable=False, server_default=""),
            sa.Column("accession", sa.String(64), nullable=False, server_default=""),
            sa.Column("action", sa.String(32), nullable=False, server_default=""),
            sa.Column("error", sa.String(256), nullable=False, server_default=""),
        )
        op.create_index("ix_hl7_message_ts", "hl7_message", ["ts"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    if "hl7_message" in tables:
        op.drop_table("hl7_message")
    if "local_worklist_item" in tables:
        op.drop_table("local_worklist_item")
