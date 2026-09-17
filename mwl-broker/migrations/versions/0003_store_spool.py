"""add the C-STORE spool

Revision ID: 0003_store_spool
Revises: 0002_cache_columns
Create Date: 2026-09-17

Store-and-forward queue: metadata in the database, the DICOM payload on disk.
Defensive by design (see 0001_baseline): a fresh database already has the table
from `create_all`, so this revision checks first.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_store_spool"
down_revision = "0002_cache_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "store_spool" in inspector.get_table_names():
        return
    op.create_table(
        "store_spool",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sop_instance_uid", sa.String(128), nullable=False),
        sa.Column("study_uid", sa.String(128), nullable=False, server_default=""),
        sa.Column("accession", sa.String(64), nullable=False, server_default=""),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("target_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("payload_path", sa.String(512), nullable=False, server_default=""),
        sa.Column("payload_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_store_spool_sop_instance_uid", "store_spool", ["sop_instance_uid"],
                    unique=True)
    op.create_index("ix_store_spool_study_uid", "store_spool", ["study_uid"])
    op.create_index("ix_store_spool_accession", "store_spool", ["accession"])
    op.create_index("ix_store_spool_status", "store_spool", ["status"])
    op.create_index("ix_store_spool_next_attempt_at", "store_spool", ["next_attempt_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "store_spool" in inspector.get_table_names():
        op.drop_table("store_spool")
