"""per source: leave QueryRetrieveLevel out of the forwarded C-FIND identifier

Revision ID: 0015_strip_qrl
Revises: 0014_ha_claim
Create Date: 2026-09-23

The broker forwards a modality's C-FIND identifier to its sources unchanged —
that is what keeps the modality's filters intact. Some foreign MWL SCPs, though,
treat `QueryRetrieveLevel (0008,0052)` as a **matching key**; since their
worklist items do not carry that attribute, they answer **nothing**. (DVTk's RIS
emulator does this; some SCUs send the attribute — a pynetdicom SCU did in our
measurement, DCMTK's `findscu -W` does not.) It is not part of the Modality Worklist
information model, so dropping it per source is standard-conforming — but it is
an explicit decision, not a silent rewrite: default off.

Defensive like every revision after the baseline (see 0001_baseline).
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_strip_qrl"
down_revision = "0014_ha_claim"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "mwl_source" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("mwl_source")}
    if "strip_query_retrieve_level" not in columns:
        op.add_column(
            "mwl_source",
            sa.Column("strip_query_retrieve_level", sa.Boolean(),
                      nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "mwl_source" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("mwl_source")}
    if "strip_query_retrieve_level" in columns:
        op.drop_column("mwl_source", "strip_query_retrieve_level")
