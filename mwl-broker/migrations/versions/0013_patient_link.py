"""distinguish a patient identifier merge from a link (ADT A40 vs A24)

Revision ID: 0013_patient_link
Revises: 0012_patient_merge
Create Date: 2026-09-22

An `A40` retires the old identifier, an `A24` only links the two records — both
live in `patient_merge`, and the difference decides whether the worklist answer
may be rewritten. Existing rows are merges, which is what the column default says.

Defensive like every revision after the baseline (see 0001_baseline): a fresh
database already carries the column through `create_all`.
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_patient_link"
down_revision = "0012_patient_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "patient_merge" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("patient_merge")}
    if "kind" in columns:
        return
    op.add_column(
        "patient_merge",
        sa.Column("kind", sa.String(16), nullable=False, server_default="merge"),
    )
    op.create_index("ix_patient_merge_kind", "patient_merge", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_patient_merge_kind", table_name="patient_merge")
    op.drop_column("patient_merge", "kind")
