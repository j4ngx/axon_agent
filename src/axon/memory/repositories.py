"""Repository layer for conversation memory.

All SQL access is encapsulated here.  The agent, tools, and Telegram handlers
never import SQLAlchemy or write raw SQL — they call the repository methods.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from axon.memory.models import Message

logger = logging.getLogger(__name__)


class ChatHistoryRepository:
    """Read/write access to conversation history stored in SQLite.

    Args:
        session_factory: An ``async_sessionmaker`` that produces async sessions.
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def save_message(
        self,
        user_id: int,
        role: str,
        content: str,
        timestamp: datetime | None = None,
    ) -> Message:
        """Persist a single message.

        Args:
            user_id: Telegram user ID.
            role: Message role (``user``, ``assistant``, ``system``, ``tool``).
            content: The message text.
            timestamp: Optional explicit timestamp; defaults to *now (UTC)*.

        Returns:
            The persisted ``Message`` instance (with ``id`` populated).
        """
        msg = Message(
            user_id=user_id,
            role=role,
            content=content,
            timestamp=timestamp or datetime.now(UTC),
        )
        async with self._session_factory() as session:
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
        logger.debug("Saved message", extra={"user_id": user_id, "role": role})
        return msg

    async def get_recent_history(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[Message]:
        """Fetch the most recent messages for a user, ordered oldest-first.

        Args:
            user_id: Telegram user ID whose history to retrieve.
            limit: Maximum number of messages to return.

        Returns:
            A list of ``Message`` instances ordered by ascending timestamp.
        """
        stmt = (
            select(Message)
            .where(Message.user_id == user_id)
            .order_by(Message.timestamp.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            messages = list(result.scalars().all())

        # Return oldest-first so the LLM sees chronological order.
        messages.reverse()
        return messages
