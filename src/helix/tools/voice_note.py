"""Built-in tool: voice_note — list, search, and delete saved voice notes.

Voice notes are auto-saved in the Telegram handler when a voice message
is received.  This tool provides read/search/delete access.
"""

from __future__ import annotations

import logging
from typing import Any

from helix.memory.voice_note_repository import VoiceNoteRepository
from helix.tools.base import Tool

logger = logging.getLogger(__name__)


class VoiceNoteTool(Tool):
    """List, search, and delete saved voice notes."""

    def __init__(self, repository: VoiceNoteRepository) -> None:
        self._repo = repository

    @property
    def name(self) -> str:
        return "voice_note"

    @property
    def description(self) -> str:
        return (
            "Manage saved voice-message transcriptions. "
            "Commands: 'list' (show recent notes), "
            "'search' (find notes by text), "
            "'delete' (remove a note)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["list", "search", "delete"],
                    "description": "The action to perform.",
                },
                "query": {
                    "type": "string",
                    "description": "Search text (required for 'search').",
                },
                "note_id": {
                    "type": "string",
                    "description": "Voice note ID (required for 'delete').",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max notes to return for 'list' (default: 10).",
                },
            },
            "required": ["command"],
        }

    async def run(self, **kwargs: Any) -> str:
        """Dispatch to the appropriate sub-command."""
        command = kwargs.get("command", "")
        user_id: int = kwargs.get("_user_id", 0)

        if not user_id:
            return "Error: could not determine user identity."

        if command == "list":
            return await self._list(user_id, kwargs)
        if command == "search":
            return await self._search(user_id, kwargs)
        if command == "delete":
            return await self._delete(user_id, kwargs)

        return f"Error: unknown command '{command}'. Use 'list', 'search', or 'delete'."

    async def _list(self, user_id: int, kwargs: dict[str, Any]) -> str:
        """List recent voice notes."""
        limit = int(kwargs.get("limit", 10))
        notes = await self._repo.get_notes(user_id, limit=limit)
        if not notes:
            return "No voice notes saved yet. Send a voice message to start."

        lines = ["🎙️ **Voice Notes**:"]
        for n in notes:
            date_str = n.created_at.strftime("%Y-%m-%d %H:%M")
            preview = n.text[:80] + "…" if len(n.text) > 80 else n.text
            lines.append(f"  `{n.id}` [{date_str}] {preview}")

        return "\n".join(lines)

    async def _search(self, user_id: int, kwargs: dict[str, Any]) -> str:
        """Search voice notes by text content."""
        query = kwargs.get("query", "").strip()
        if not query:
            return "Error: 'query' is required for search."

        results = await self._repo.search(user_id, query)
        if not results:
            return f"No voice notes matching '{query}'."

        lines = [f"🔍 **Results for** _{query}_:"]
        for n in results:
            date_str = n.created_at.strftime("%Y-%m-%d %H:%M")
            preview = n.text[:80] + "…" if len(n.text) > 80 else n.text
            lines.append(f"  `{n.id}` [{date_str}] {preview}")

        return "\n".join(lines)

    async def _delete(self, user_id: int, kwargs: dict[str, Any]) -> str:
        """Delete a voice note."""
        note_id = kwargs.get("note_id", "").strip()
        if not note_id:
            return "Error: 'note_id' is required. Use 'list' to see your notes."

        deleted = await self._repo.delete(user_id, note_id)
        if not deleted:
            return f"Voice note `{note_id}` not found."
        return f"✅ Voice note `{note_id}` deleted."
