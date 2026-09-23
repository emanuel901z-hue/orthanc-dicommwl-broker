"""store log: legacy rows carry NULL in applied_transforms — fill them

Revision ID: 0016_store_log_transforms
Revises: 0015_strip_qrl
Create Date: 2026-09-23

The column was added to an existing table, so rows written before it existed
have NULL. The response model wants a list, which made `GET /api/v1/logs/stores`
answer **500** as soon as a limit reached such a row — unnoticed because no view
read the endpoint until the store log got its UI element. The schema now coerces
NULL to `[]` as well; this revision makes the stored data consistent.

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_store_log_transforms"
down_revision = "0015_strip_qrl"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "store_log" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("store_log")}
    if "applied_transforms" in columns:
        op.execute(sa.text(
            "UPDATE store_log SET applied_transforms = '[]' "
            "WHERE applied_transforms IS NULL"
        ))


def downgrade() -> None:
    # no way back: NULL and [] are not distinguishable afterwards, and both mean
    # "no transform rule applied"
    pass
