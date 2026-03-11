"""Repository layer for reminder persistence.

Firestore data model
--------------------
``users/{user_id}/reminders/{reminder_id}``
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import AsyncClient

from helix.memory.models import Reminder

logger = logging.getLogger(__name__)


class ReminderRepository:
    """Read/write access to reminders stored in Firestore.

    Args:
        client: An async Firestore client.
    """

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    def _reminders_ref(self, user_id: int) -> Any:
        """Return the ``reminders`` sub-collection for *user_id*."""
        return self._client.collection("users").document(str(user_id)).collection("reminders")

    async def create_reminder(self, reminder: Reminder) -> str:
        """Persist a new reminder and return its document ID.

        Args:
            reminder: The reminder to save.

        Returns:
            The auto-generated Firestore document ID.
        """
        ref = self._reminders_ref(reminder.user_id)
        doc_ref = ref.document()
        await doc_ref.set(reminder.to_dict())
        logger.info(
            "Reminder created",
            extra={"user_id": reminder.user_id, "doc_id": doc_ref.id},
        )
        return doc_ref.id

    async def get_pending_reminders(self, user_id: int) -> list[Reminder]:
        """Return all pending reminders for a user, ordered by trigger time.

        Args:
            user_id: Telegram user ID.

        Returns:
            A list of pending ``Reminder`` instances.
        """
        ref = self._reminders_ref(user_id)
        query = ref.where("status", "==", "pending").order_by("trigger_at")
        docs = await query.get()
        return [Reminder.from_dict(doc.to_dict(), doc.id) for doc in docs]

    async def cancel_reminder(self, user_id: int, reminder_id: str) -> bool:
        """Mark a reminder as cancelled.

        Args:
            user_id: Telegram user ID.
            reminder_id: Firestore document ID of the reminder.

        Returns:
            ``True`` if the reminder was found and cancelled, ``False`` otherwise.
        """
        doc_ref = self._reminders_ref(user_id).document(reminder_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False
        await doc_ref.update({"status": "cancelled"})
        logger.info(
            "Reminder cancelled",
            extra={"user_id": user_id, "reminder_id": reminder_id},
        )
        return True

    async def get_due_reminders(self) -> list[Reminder]:
        """Return all pending reminders whose trigger time has passed.

        Uses a collection group query across all users.

        Returns:
            A list of due ``Reminder`` instances.
        """
        now = datetime.now(UTC)
        query = (
            self._client.collection_group("reminders")
            .where("status", "==", "pending")
            .where("trigger_at", "<=", now)
        )
        docs = await query.get()
        return [Reminder.from_dict(doc.to_dict(), doc.id) for doc in docs]

    async def mark_completed(self, user_id: int, reminder_id: str) -> None:
        """Mark a reminder as completed.

        Args:
            user_id: Telegram user ID.
            reminder_id: Firestore document ID.
        """
        doc_ref = self._reminders_ref(user_id).document(reminder_id)
        await doc_ref.update({"status": "completed"})
        logger.info(
            "Reminder completed",
            extra={"user_id": user_id, "reminder_id": reminder_id},
        )

    async def update_next_trigger(
        self, user_id: int, reminder_id: str, next_trigger: datetime
    ) -> None:
        """Update the trigger time for a recurring reminder.

        Args:
            user_id: Telegram user ID.
            reminder_id: Firestore document ID.
            next_trigger: The next trigger datetime.
        """
        doc_ref = self._reminders_ref(user_id).document(reminder_id)
        await doc_ref.update({"trigger_at": next_trigger})
        logger.info(
            "Reminder rescheduled",
            extra={
                "user_id": user_id,
                "reminder_id": reminder_id,
                "next_trigger": next_trigger.isoformat(),
            },
        )
