"""IndexerConfig ORM model."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IndexerConfig(Base):
    __tablename__ = "indexer_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Prowlarr")
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    categories: Mapped[str] = mapped_column(String(100), nullable=False, default="7010,7020")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
