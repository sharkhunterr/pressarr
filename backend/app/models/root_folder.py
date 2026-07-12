"""RootFolder ORM model."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RootFolder(Base):
    __tablename__ = "root_folder"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    magazines: Mapped[list["Magazine"]] = relationship(back_populates="root_folder")
