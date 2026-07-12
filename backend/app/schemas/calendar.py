"""Calendar and forecast Pydantic schemas."""
from datetime import date

from app.schemas import CamelModel


class CalendarResource(CamelModel):
    issue_id: int | None = None
    magazine_id: int
    magazine_title: str
    cover_url: str | None = None
    date: date
    number: int | None = None
    status: str
    is_forecast: bool = False
