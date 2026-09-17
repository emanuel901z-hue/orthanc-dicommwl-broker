"""baseline — schema as it existed before versioned migrations

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-17

This revision is **stamped, never executed**:

* A fresh installation gets its base schema from `Base.metadata.create_all()`
  (the models are the single source of truth), and `db.init_db()` then stamps
  this revision before upgrading to head.
* An existing installation (created before Alembic existed) has the same base
  schema and is stamped the same way.

Consequence for every later revision: it must be **defensive** — check whether
its change is already present, because a fresh database already carries the
current schema when the revision runs.
"""
from alembic import op
import sqlalchemy as sa  # noqa: F401

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op: the base schema comes from the models (`create_all`)."""


def downgrade() -> None:
    """Nothing to undo — the baseline is never executed."""
