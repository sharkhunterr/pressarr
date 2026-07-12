"""add magazine enrichment fields (ISSN-first cascade)

Adds nullable enrichment columns on the existing ``magazine`` table so
results from the ZDB / Wikidata / BnF / LoC cascade can be persisted
when the operator promotes a cascade hit into a monitored magazine.
None of the new columns are required — the cascade is best-effort.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('magazine', schema=None) as batch_op:
        # ISO-639-1 language code (e.g. "en", "fr"). Useful for the
        # indexer/parser to filter releases to the right edition when a
        # title has parallel translations.
        batch_op.add_column(sa.Column('language', sa.String(length=2), nullable=True))
        # Provider backlinks — opaque IDs we don't query on but keep
        # for refresh / debugging.
        batch_op.add_column(sa.Column('wikidata_qid', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('zdb_id', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('wikipedia_url', sa.String(length=500), nullable=True))
        # Categories: comma-separated coarse labels (press, newspaper,
        # scientific, sports, …). Kept as a flat string for sqlite
        # compatibility; downstream code splits on ','.
        batch_op.add_column(sa.Column('categories', sa.String(length=500), nullable=True))
        # Year-precision dates — full ISO date is rarely available
        # for older serials and we only ever surface the year.
        batch_op.add_column(sa.Column('first_issued', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('ceased_at', sa.String(length=10), nullable=True))
        # Provenance: enum-shaped string (pending / partial / complete)
        # that flags whether the cascade managed to populate the rich
        # fields. Defaults to 'pending' for backfilled rows so the
        # next scheduled refresh re-runs the cascade for them.
        batch_op.add_column(
            sa.Column(
                'enrichment_status',
                sa.String(length=16),
                nullable=False,
                server_default='pending',
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('magazine', schema=None) as batch_op:
        for col in (
            'enrichment_status',
            'ceased_at',
            'first_issued',
            'categories',
            'wikipedia_url',
            'zdb_id',
            'wikidata_qid',
            'language',
        ):
            batch_op.drop_column(col)
