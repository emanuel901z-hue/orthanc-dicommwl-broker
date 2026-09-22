"""two broker instances on one database: the spool claim and the instance heartbeat

Revision ID: 0014_ha_claim
Revises: 0013_patient_link
Create Date: 2026-09-22

High availability needs two things that cannot live in the head of a process:
a **claim** on a spool entry (so two instances do not deliver the same image
twice) and a **heartbeat** per instance (so the operator sees who is running).
Existing spool rows are unclaimed, which is what the defaults say.

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_ha_claim"
down_revision = "0013_patient_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()

    if "store_spool" in tables:
        columns = {column["name"] for column in inspector.get_columns("store_spool")}
        if "claimed_by" not in columns:
            op.add_column("store_spool", sa.Column("claimed_by", sa.String(64),
                                                   nullable=False, server_default=""))
            op.create_index("ix_store_spool_claimed_by", "store_spool", ["claimed_by"])
        if "lease_until" not in columns:
            op.add_column("store_spool", sa.Column("lease_until",
                                                   sa.DateTime(timezone=True), nullable=True))
            op.create_index("ix_store_spool_lease_until", "store_spool", ["lease_until"])

    if "broker_instance" not in tables:
        op.create_table(
            "broker_instance",
            sa.Column("instance_id", sa.String(64), primary_key=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
            sa.Column("version", sa.String(32), nullable=False, server_default=""),
            sa.Column("hostname", sa.String(128), nullable=False, server_default=""),
            sa.Column("pid", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_broker_instance_last_seen", "broker_instance", ["last_seen"])


def downgrade() -> None:
    op.drop_table("broker_instance")
    op.drop_index("ix_store_spool_lease_until", table_name="store_spool")
    op.drop_index("ix_store_spool_claimed_by", table_name="store_spool")
    op.drop_column("store_spool", "lease_until")
    op.drop_column("store_spool", "claimed_by")
