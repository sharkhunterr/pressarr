"""add request_type + one-shot targets to magazine

Adds three columns on the ``magazine`` table so allseerr can
ask for either a recurring subscription (the previous default
shape) or a single back-issue:

- ``request_type`` = 'subscription' | 'one_shot' (NOT NULL,
  default 'subscription')
- ``target_issue_label`` = operator-typed issue id when one_shot
  (nullable)
- ``target_issue_date`` = ISO date when the issue is identified
  by publication date instead of a number (nullable)

The auto-grab scheduler (next commit) reads these to decide
whether to keep monitoring a magazine after the first grab.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("magazine", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "request_type",
                sa.String(length=16),
                nullable=False,
                server_default="subscription",
            )
        )
        batch_op.add_column(
            sa.Column(
                "target_issue_label",
                sa.String(length=100),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("target_issue_date", sa.Date(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("magazine", schema=None) as batch_op:
        batch_op.drop_column("target_issue_date")
        batch_op.drop_column("target_issue_label")
        batch_op.drop_column("request_type")
