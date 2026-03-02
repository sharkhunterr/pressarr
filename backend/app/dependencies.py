"""FastAPI Depends() providers."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

import app.database as db_module
from app.config import Config

_config: Config | None = None


def get_config() -> Config:
    """Return the application config singleton."""
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config


def set_config(config: Config) -> None:
    """Set the application config singleton (called at startup)."""
    global _config
    _config = config


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session with commit/rollback."""
    if db_module.async_session_factory is None:
        raise RuntimeError("Database not initialized")
    async with db_module.async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
