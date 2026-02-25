"""Initial migration — empty schema.

Revision ID: 001
Revises:
Create Date: 2026-02-25
"""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Empty schema — no tables yet. Future features will add Magazine, Issue, IssueFile."""
    pass


def downgrade() -> None:
    pass
