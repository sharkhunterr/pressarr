"""add use_latest_issue_cover column to magazine

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-27 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('magazine', schema=None) as batch_op:
        batch_op.add_column(sa.Column('use_latest_issue_cover', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('magazine', schema=None) as batch_op:
        batch_op.drop_column('use_latest_issue_cover')
