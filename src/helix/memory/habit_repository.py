"""Repository layer for habit persistence.

Firestore data model
--------------------
``users/{user_id}/habits/{habit_id}``
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import AsyncClient

from helix.memory.models import Habit

logger = logging.getLogger(__name__)


class HabitRepository:
    """Read/write access to habits stored in Firestore.

    Args:
        client: An async Firestore client.
    """

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    def _habits_ref(self, user_id: int) -> Any:
        """Return the ``habits`` sub-collection for *user_id*."""
        return self._client.collection("users").document(str(user_id)).collection("habits")

    async def create_habit(self, habit: Habit) -> str:
        """Persist a new habit and return its document ID.

        Args:
            habit: The habit to save.

        Returns:
            The auto-generated Firestore document ID.
        """
        ref = self._habits_ref(habit.user_id)
        doc_ref = ref.document()
        await doc_ref.set(habit.to_dict())
        logger.info(
            "Habit created",
            extra={"user_id": habit.user_id, "doc_id": doc_ref.id},
        )
        return doc_ref.id

    async def get_active_habits(self, user_id: int) -> list[Habit]:
        """Return all active habits for a user.

        Args:
            user_id: Telegram user ID.

        Returns:
            A list of active ``Habit`` instances.
        """
        ref = self._habits_ref(user_id)
        query = ref.where("active", "==", True).order_by("created_at")
        docs = await query.get()
        return [Habit.from_dict(doc.to_dict(), doc.id) for doc in docs]

    async def log_completion(self, user_id: int, habit_id: str) -> Habit | None:
        """Record a habit completion and update streak counters.

        Args:
            user_id: Telegram user ID.
            habit_id: Firestore document ID.

        Returns:
            The updated ``Habit`` if found, ``None`` otherwise.
        """
        doc_ref = self._habits_ref(user_id).document(habit_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return None

        habit = Habit.from_dict(doc.to_dict(), doc.id)
        today = datetime.now(UTC).date()

        # Avoid double-logging the same day
        if habit.last_completed == today:
            return habit

        # Check if streak is still alive; if not, reset
        if habit.check_streak(today):
            habit.current_streak += 1
        else:
            habit.current_streak = 1

        habit.last_completed = today
        if habit.current_streak > habit.best_streak:
            habit.best_streak = habit.current_streak

        await doc_ref.update(
            {
                "current_streak": habit.current_streak,
                "best_streak": habit.best_streak,
                "last_completed": today.isoformat(),
            }
        )
        logger.info(
            "Habit completed",
            extra={
                "user_id": user_id,
                "habit_id": habit_id,
                "streak": habit.current_streak,
            },
        )
        return habit

    async def deactivate_habit(self, user_id: int, habit_id: str) -> bool:
        """Deactivate (soft-delete) a habit.

        Args:
            user_id: Telegram user ID.
            habit_id: Firestore document ID.

        Returns:
            ``True`` if the habit was found and deactivated, ``False`` otherwise.
        """
        doc_ref = self._habits_ref(user_id).document(habit_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False
        await doc_ref.update({"active": False})
        logger.info(
            "Habit deactivated",
            extra={"user_id": user_id, "habit_id": habit_id},
        )
        return True
