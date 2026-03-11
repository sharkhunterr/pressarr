"""IndexerConfig ORM model."""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IndexerConfig(Base):
    __tablename__ = "indexer_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Prowlarr")
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    categories: Mapped[str] = mapped_column(String(100), nullable=False, default="7000,7010,7020")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # JSON mapping of prowlarr indexer overrides:
    # {"<prowlarr_id>": {"enabled": bool, "categories": "7000,7010"}}
    indexer_overrides: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
