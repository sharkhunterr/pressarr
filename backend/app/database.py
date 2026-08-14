"""Async SQLAlchemy engine and session factory for SQLite."""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


engine = None
async_session_factory = None


async def init_database(db_path: str) -> None:
    """Initialize the async engine and session factory."""
    global engine, async_session_factory

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        # 30 s au lieu de 5 s — le pack dispatch (analyse IA sur N
        # fichiers pendant plusieurs minutes) + le monitor scheduler
        # (tous les 30 s) + les writes ai_enrichment_run + les imports
        # se battaient pour la même DB. 5 s ne suffisait pas quand
        # plusieurs writers arrivaient simultanément.
        cursor.execute("PRAGMA busy_timeout=30000")
        # NORMAL synchronous : sync uniquement au checkpoint WAL, pas
        # à chaque commit. Baisse la durée des writes de ~10× sur
        # SSD. Trade-off : perte des writes des dernières ms en cas
        # de coupure de courant — pour de l'observabilité c'est OK.
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_database() -> None:
    """Dispose of the engine."""
    global engine
    if engine:
        await engine.dispose()


async def get_session() -> AsyncSession:
    """Yield an async session."""
    if async_session_factory is None:
        raise RuntimeError("Database not initialized")
    async with async_session_factory() as session:
        yield session
