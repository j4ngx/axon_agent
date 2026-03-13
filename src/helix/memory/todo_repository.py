"""Repository layer for todo persistence.

Firestore data model
--------------------
``users/{user_id}/todos/{todo_id}``
"""

from __future__ import annotations

import logging
from typing import Any

from google.cloud.firestore import AsyncClient

from helix.memory.models import Todo

logger = logging.getLogger(__name__)


class TodoRepository:
    """Read/write access to todos stored in Firestore.

    Args:
        client: An async Firestore client.
    """

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    def _todos_ref(self, user_id: int) -> Any:
        """Return the ``todos`` sub-collection for *user_id*."""
        return self._client.collection("users").document(str(user_id)).collection("todos")

    async def create_todo(self, todo: Todo) -> str:
        """Persist a new todo and return its document ID.

        Args:
            todo: The todo to save.

        Returns:
            The auto-generated Firestore document ID.
        """
        ref = self._todos_ref(todo.user_id)
        doc_ref = ref.document()
        await doc_ref.set(todo.to_dict())
        logger.info(
            "Todo created",
            extra={"user_id": todo.user_id, "doc_id": doc_ref.id},
        )
        return doc_ref.id

    async def get_todos(self, user_id: int, status: str = "pending") -> list[Todo]:
        """Return todos for a user filtered by status.

        Args:
            user_id: Telegram user ID.
            status: Status to filter by (default ``pending``).

        Returns:
            A list of ``Todo`` instances.
        """
        ref = self._todos_ref(user_id)
        query = ref.where("status", "==", status).order_by("created_at")
        docs = await query.get()
        return [Todo.from_dict(doc.to_dict(), doc.id) for doc in docs]

    async def complete_todo(self, user_id: int, todo_id: str) -> bool:
        """Mark a todo as completed.

        Args:
            user_id: Telegram user ID.
            todo_id: Firestore document ID of the todo.

        Returns:
            ``True`` if the todo existed, ``False`` otherwise.
        """
        doc_ref = self._todos_ref(user_id).document(todo_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False
        from datetime import UTC, datetime

        await doc_ref.update({"status": "completed", "completed_at": datetime.now(UTC)})
        logger.info(
            "Todo completed",
            extra={"user_id": user_id, "todo_id": todo_id},
        )
        return True

    async def delete_todo(self, user_id: int, todo_id: str) -> bool:
        """Delete a todo.

        Args:
            user_id: Telegram user ID.
            todo_id: Firestore document ID.

        Returns:
            ``True`` if the todo existed and was deleted, ``False`` otherwise.
        """
        doc_ref = self._todos_ref(user_id).document(todo_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False
        await doc_ref.delete()
        logger.info(
            "Todo deleted",
            extra={"user_id": user_id, "todo_id": todo_id},
        )
        return True
