"""make issue_file.issue_id nullable and add magazine_id

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Populate magazine_id from the linked issue before making issue_id nullable
    with op.batch_alter_table('issue_file', schema=None) as batch_op:
        batch_op.add_column(sa.Column('magazine_id', sa.Integer(), nullable=True))

    # Backfill magazine_id from the related issue
    op.execute(
        "UPDATE issue_file SET magazine_id = ("
        "  SELECT issue.magazine_id FROM issue WHERE issue.id = issue_file.issue_id"
        ")"
    )

    # Now make magazine_id non-nullable and add FK + make issue_id nullable
    with op.batch_alter_table('issue_file', schema=None) as batch_op:
        batch_op.alter_column('magazine_id', nullable=False)
        batch_op.create_foreign_key(
            'fk_issue_file_magazine_id', 'magazine', ['magazine_id'], ['id']
        )
        batch_op.alter_column('issue_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Re-assign orphan files or delete them before making issue_id non-nullable
    op.execute("DELETE FROM issue_file WHERE issue_id IS NULL")

    with op.batch_alter_table('issue_file', schema=None) as batch_op:
        batch_op.alter_column('issue_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_constraint('fk_issue_file_magazine_id', type_='foreignkey')
        batch_op.drop_column('magazine_id')
