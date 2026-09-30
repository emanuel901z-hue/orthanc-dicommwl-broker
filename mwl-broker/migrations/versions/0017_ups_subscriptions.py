"""UPS-RS subscriptions: who wants to hear about work item state changes

Revision ID: 0017_ups_subscriptions
Revises: 0016_store_log_transforms
Create Date: 2026-09-30

PS3.18 §11.6 lets a client subscribe to work item state changes instead of
polling. The subscription itself is configuration (a subscriber AE title and an
optional work item UID), so it lives in the database next to the rest.

Defensive like every revision after the baseline (see 0001_baseline): a fresh
database already has the table from `create_all`, so only create it when it is
missing.
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_ups_subscriptions"
down_revision = "0016_store_log_transforms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "ups_subscription" in inspector.get_table_names():
        return
    op.create_table(
        "ups_subscription",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscriber_aet", sa.String(16), nullable=False),
        sa.Column("workitem_uid", sa.String(128), nullable=False, server_default=""),
        sa.Column("deletion_lock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ups_subscription_subscriber_aet", "ups_subscription",
                    ["subscriber_aet"], unique=True)
    op.create_index("ix_ups_subscription_workitem_uid", "ups_subscription",
                    ["workitem_uid"])


def downgrade() -> None:
    op.drop_index("ix_ups_subscription_workitem_uid", table_name="ups_subscription")
    op.drop_index("ix_ups_subscription_subscriber_aet", table_name="ups_subscription")
    op.drop_table("ups_subscription")
