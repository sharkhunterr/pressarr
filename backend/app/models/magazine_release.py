"""MagazineRelease ORM model.

Persists one row per scene release scraped from a magazine
indexer (Bookys, telecharger-magazines.org, …). A release is a
specific downloadable package — typically one issue of a
publication — pointing to one or more file-hosters
(1fichier / Uploaded / Nitroflare / RapidGator / …) where the
actual PDF lives.

Lifecycle:
- ``status='available'`` — discovered, not yet grabbed
- ``status='grabbed'``   — handed off to the download client
                           (JDownloader 2 / debrid / etc.)
- ``status='imported'``  — file has landed in the library
- ``status='failed'``    — download client gave up

Dedup happens via ``source`` + ``source_url`` (one row per
release per indexer). Two indexers can publish the same release
— that's fine, they get separate rows so the operator can pick
whichever hoster set they prefer.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MagazineRelease(Base):
    __tablename__ = "magazine_release"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    magazine_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("magazine.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Which indexer scraped the release. Used for dedup + filter
    # ("only show me Bookys releases").
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    # The HTML page on the indexer site that exposed this
    # release. Used both for dedup (uniq with ``source``) and as
    # the operator-clickable "open on source" link.
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)

    # As advertised on the indexer — preserved as-is for display.
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Best-effort issue label parsed from the title ("N°123",
    # "HS 4", "2026-04"). Null when the parser doesn't find one.
    issue_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Best-effort year parsed from title / publish date.
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # File format ("pdf", "epub", "cbz", …). The vast majority
    # of scraped magazines are PDF; kept stringy for flexibility.
    file_format: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Indexer-advertised size in bytes. Optional — Bookys
    # sometimes omits it on the listing page.
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Optional indexer-side publish date (ISO 8601 string,
    # kept loose to accommodate "Il y a 2 jours" / "2026-04-12"
    # styles that we normalise opportunistically).
    published_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # JSON-encoded list of ``{hoster, url}`` dicts. Kept as Text
    # for SQLite portability (Postgres can use JSONB later; the
    # accessor at app/services/magazine_release_service.py
    # handles encode/decode). Required — a release with no
    # hosters has nothing to download.
    hoster_links: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="available"
    )
    # When the operator clicked Grab. Drives the dispatcher
    # poll loop; null = never dispatched.
    grabbed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    # Free-text message from the dispatcher when something
    # goes wrong ("1fichier captcha", "all hosters returned
    # 404", …). Surfaced in the UI.
    status_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "source", "source_url", name="uq_magazine_release_source"
        ),
        Index("ix_magazine_release_magazine_id", "magazine_id"),
        Index("ix_magazine_release_status", "status"),
    )
