"""Issue and issue file Pydantic schemas."""

from datetime import date, datetime
from typing import Any

from pydantic import model_validator

from app.schemas import CamelModel


class IssueFileResource(CamelModel):
    id: int
    path: str
    relative_path: str
    size: int
    format: str
    quality: str
    original_filename: str
    release_group: str | None = None
    language: str | None = None
    imported_at: datetime
    # Origine de l'import — utile pour l'UI ("Importé depuis pack X
    # le 15/08/2026") et pour reanalyze IA (savoir quel torrent_name
    # utiliser : original_filename pour un fichier de pack,
    # source_release_title pour un torrent standalone).
    source_type: str = "torrent"
    source_pack_id: int | None = None
    source_pack_name: str | None = None
    source_release_title: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _extract_pack_name(cls, data: Any) -> Any:
        """Extrait le nom du pack depuis la relation ``source_pack``
        pour éviter de forcer l'appelant à composer manuellement le
        dict avant sérialisation. Fonctionne quand data est un ORM
        object (IssueFile chargé avec selectinload) ou un dict."""
        if hasattr(data, "source_pack"):
            pack = getattr(data, "source_pack", None)
            if pack is not None and not getattr(data, "source_pack_name", None):
                data.source_pack_name = getattr(pack, "name", None)
        elif isinstance(data, dict):
            pack = data.get("source_pack")
            if pack is not None and not data.get("source_pack_name"):
                data["source_pack_name"] = (
                    pack.get("name") if isinstance(pack, dict)
                    else getattr(pack, "name", None)
                )
        return data


class IssueResource(CamelModel):
    id: int
    magazine_id: int
    number: int | None = None
    volume: int | None = None
    title: str | None = None
    subtitle: str | None = None
    price: str | None = None
    publication_date: date | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    status: str
    monitored: bool
    is_special: bool
    is_forecast: bool
    cover_path: str | None = None
    added_at: datetime
    issn: str | None = None
    file: IssueFileResource | None = None


class IssueUpdateRequest(CamelModel):
    """Partial update for an issue. Only provided fields are updated."""
    number: int | None = None
    volume: int | None = None
    title: str | None = None
    subtitle: str | None = None
    price: str | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    monitored: bool | None = None
    is_special: bool | None = None
    status: str | None = None
    issn: str | None = None
    # File fields (applied when issue has a file)
    quality: str | None = None
    format: str | None = None
    release_group: str | None = None
    language: str | None = None
    original_filename: str | None = None


class IssueReassignRequest(CamelModel):
    target_issue_id: int | None = None


class FileAssignRequest(CamelModel):
    file_id: int
    target_issue_id: int


class IssueBatchMonitorRequest(CamelModel):
    issue_ids: list[int]
    monitored: bool
