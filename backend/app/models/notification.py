"""Notification ORM model."""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(20), nullable=False)
    settings: Mapped[str] = mapped_column(Text, nullable=False)
    on_grab: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    on_download: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    on_import: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    on_upgrade: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    on_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
