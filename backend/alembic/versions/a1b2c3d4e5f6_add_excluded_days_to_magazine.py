"""add excluded_days column to magazine

Revision ID: a1b2c3d4e5f6
Revises: 2ad64e37a608
Create Date: 2026-02-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '2ad64e37a608'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('magazine', schema=None) as batch_op:
        batch_op.add_column(sa.Column('excluded_days', sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('magazine', schema=None) as batch_op:
        batch_op.drop_column('excluded_days')
