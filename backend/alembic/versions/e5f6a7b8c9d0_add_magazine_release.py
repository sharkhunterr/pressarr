"""add magazine_release table for scene indexer hits

Creates the ``magazine_release`` table that stores one row per
release scraped from a configured scene indexer (Bookys,
telecharger-magazines.org, …). Each row points to a list of
file-hosters where the actual file lives. Required for the
download dispatcher (JDownloader 2 folder watch) to know what
to grab.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-03
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "magazine_release",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "magazine_id",
            sa.Integer(),
            sa.ForeignKey("magazine.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("issue_label", sa.String(length=100), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("file_format", sa.String(length=8), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.String(length=32), nullable=True),
        sa.Column("cover_url", sa.String(length=1000), nullable=True),
        sa.Column("hoster_links", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="available",
        ),
        sa.Column("grabbed_at", sa.DateTime(), nullable=True),
        sa.Column("status_message", sa.String(length=500), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "source", "source_url", name="uq_magazine_release_source"
        ),
    )
    op.create_index(
        "ix_magazine_release_magazine_id",
        "magazine_release",
        ["magazine_id"],
    )
    op.create_index(
        "ix_magazine_release_status",
        "magazine_release",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_magazine_release_status", table_name="magazine_release")
    op.drop_index(
        "ix_magazine_release_magazine_id", table_name="magazine_release"
    )
    op.drop_table("magazine_release")
