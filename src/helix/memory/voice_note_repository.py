"""Repository layer for voice note persistence.

Firestore data model
--------------------
``users/{user_id}/voice_notes/{note_id}``
"""

from __future__ import annotations

import logging
from typing import Any

from google.cloud.firestore import AsyncClient

from helix.memory.models import VoiceNote

logger = logging.getLogger(__name__)


class VoiceNoteRepository:
    """Read/write access to voice notes stored in Firestore.

    Args:
        client: An async Firestore client.
    """

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    def _ref(self, user_id: int) -> Any:
        """Return the ``voice_notes`` sub-collection for *user_id*."""
        return self._client.collection("users").document(str(user_id)).collection("voice_notes")

    async def create(self, note: VoiceNote) -> str:
        """Persist a new voice note and return its document ID."""
        doc_ref = self._ref(note.user_id).document()
        await doc_ref.set(note.to_dict())
        logger.info(
            "Voice note created",
            extra={"user_id": note.user_id, "doc_id": doc_ref.id},
        )
        return doc_ref.id

    async def get_notes(self, user_id: int, limit: int = 10) -> list[VoiceNote]:
        """Return the most recent voice notes for a user.

        Args:
            user_id: Telegram user ID.
            limit: Maximum number of notes to return.

        Returns:
            A list of ``VoiceNote`` instances, newest first.
        """
        query = self._ref(user_id).order_by("created_at", direction="DESCENDING").limit(limit)
        docs = await query.get()
        return [VoiceNote.from_dict(doc.to_dict(), doc.id) for doc in docs]

    async def search(self, user_id: int, query_text: str) -> list[VoiceNote]:
        """Search voice notes by substring match (case-insensitive).

        Firestore lacks full-text search, so we fetch all notes and
        filter in memory.  Acceptable for personal-use volumes.
        """
        all_ref = self._ref(user_id).order_by("created_at", direction="DESCENDING")
        docs = await all_ref.get()
        query_lower = query_text.lower()
        return [
            VoiceNote.from_dict(doc.to_dict(), doc.id)
            for doc in docs
            if query_lower in doc.to_dict().get("text", "").lower()
        ]

    async def delete(self, user_id: int, note_id: str) -> bool:
        """Delete a voice note. Returns ``True`` if it existed."""
        doc_ref = self._ref(user_id).document(note_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False
        await doc_ref.delete()
        logger.info(
            "Voice note deleted",
            extra={"user_id": user_id, "note_id": note_id},
        )
        return True
