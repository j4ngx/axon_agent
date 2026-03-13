"""Repository layer for smart routine persistence.

Firestore data model
--------------------
``users/{user_id}/routines/{routine_id}``
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import AsyncClient

from helix.memory.models import Routine

logger = logging.getLogger(__name__)


class RoutineRepository:
    """Read/write access to smart routines stored in Firestore.

    Args:
        client: An async Firestore client.
    """

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    def _ref(self, user_id: int) -> Any:
        """Return the ``routines`` sub-collection for *user_id*."""
        return self._client.collection("users").document(str(user_id)).collection("routines")

    async def create(self, routine: Routine) -> str:
        """Persist a new routine and return its document ID."""
        doc_ref = self._ref(routine.user_id).document()
        await doc_ref.set(routine.to_dict())
        logger.info(
            "Routine created",
            extra={"user_id": routine.user_id, "doc_id": doc_ref.id, "name": routine.name},
        )
        return doc_ref.id

    async def get_active(self, user_id: int) -> list[Routine]:
        """Return all active routines for a user."""
        query = self._ref(user_id).where("active", "==", True)
        docs = await query.get()
        return [Routine.from_dict(doc.to_dict(), doc.id) for doc in docs]

    async def get_all(self, user_id: int) -> list[Routine]:
        """Return all routines for a user."""
        docs = await self._ref(user_id).order_by("created_at", direction="DESCENDING").get()
        return [Routine.from_dict(doc.to_dict(), doc.id) for doc in docs]

    async def toggle(self, user_id: int, routine_id: str) -> bool | None:
        """Toggle a routine's active status. Returns the new state, or ``None`` if not found."""
        doc_ref = self._ref(user_id).document(routine_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return None
        current = doc.to_dict().get("active", True)
        new_state = not current
        await doc_ref.update({"active": new_state})
        logger.info(
            "Routine toggled",
            extra={"user_id": user_id, "routine_id": routine_id, "active": new_state},
        )
        return new_state

    async def delete(self, user_id: int, routine_id: str) -> bool:
        """Delete a routine. Returns ``True`` if it existed."""
        doc_ref = self._ref(user_id).document(routine_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False
        await doc_ref.delete()
        logger.info(
            "Routine deleted",
            extra={"user_id": user_id, "routine_id": routine_id},
        )
        return True

    async def update_last_triggered(self, user_id: int, routine_id: str) -> None:
        """Update the ``last_triggered`` timestamp to now."""
        doc_ref = self._ref(user_id).document(routine_id)
        await doc_ref.update({"last_triggered": datetime.now(UTC)})
