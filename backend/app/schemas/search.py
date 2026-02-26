"""Search and grab Pydantic schemas."""
from app.schemas import CamelModel


class SearchResultResource(CamelModel):
    guid: str
    title: str
    indexer: str
    size: int
    age: int  # days
    protocol: str  # "torrent" or "usenet"
    seeders: int | None = None
    quality: str = "unknown"
    language: str = "unknown"
    score: float = 0.0
    is_blocklisted: bool = False
    download_url: str


class GrabResponse(CamelModel):
    issue_id: int
    download_id: str | None = None
    message: str
