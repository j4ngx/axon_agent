"""Repository layer for conversation memory.

All database access is encapsulated here.  The agent, tools, and Telegram handlers
never write raw queries — they call the repository methods.

Firestore data model
--------------------
``users/{user_id}/messages/{message_id}``

Using per-user sub-collections means queries only need ``ORDER BY timestamp`` on a
single collection, which requires no composite index.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import AsyncClient, Query

from helix.memory.models import Message

logger = logging.getLogger(__name__)


class ChatHistoryRepository:
    """Read/write access to conversation history stored in Firestore.

    Args:
        client: An async Firestore client.
    """

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _messages_ref(self, user_id: int) -> Any:
        """Return the ``messages`` sub-collection for *user_id*."""
        return self._client.collection("users").document(str(user_id)).collection("messages")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

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

        doc_ref = self._messages_ref(user_id).document()
        await doc_ref.set(msg.to_dict())
        msg.id = doc_ref.id

        logger.debug("Saved message", extra={"user_id": user_id, "role": role, "id": msg.id})
        return msg

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_recent_history(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[Message]:
        """Fetch the most recent messages for a user, ordered oldest-first.

        Queries the ``users/{user_id}/messages`` sub-collection — no composite
        index is needed because the filter on ``user_id`` is implicit in the
        collection path.

        Args:
            user_id: Telegram user ID whose history to retrieve.
            limit: Maximum number of messages to return.

        Returns:
            A list of ``Message`` instances ordered by ascending timestamp.
        """
        query = (
            self._messages_ref(user_id)
            .order_by("timestamp", direction=Query.DESCENDING)
            .limit(limit)
        )

        docs = await query.get()
        messages = [Message.from_dict(doc.to_dict() or {}, doc.id) for doc in docs]

        # Return oldest-first so the LLM sees chronological order.
        messages.reverse()
        return messages
