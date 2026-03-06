"""Database engine and session factory helpers.

This module owns the async engine and session lifecycle.  The rest of Axon
never touches SQLAlchemy engine details directly — they go through
``repositories.py``.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from axon.memory.models import Base

logger = logging.getLogger(__name__)


def create_engine(db_path: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine for the given SQLite path.

    Args:
        db_path: Absolute or relative filesystem path to the SQLite database.

    Returns:
        A configured ``AsyncEngine`` instance.
    """
    url = f"sqlite+aiosqlite:///{db_path}"
    logger.info("Creating async database engine", extra={"url": url})
    return create_async_engine(url, echo=False)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    """Return a session factory bound to *engine*.

    Args:
        engine: The async engine to bind to.

    Returns:
        An ``async_sessionmaker`` that produces ``AsyncSession`` instances.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Create all tables that do not yet exist.

    This is safe to call on every startup — SQLAlchemy's
    ``create_all`` is a no-op for tables that are already present.

    Args:
        engine: The async engine whose database should be initialised.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialised")
