"""Built-in tool: note — create, list, search, and read local Markdown notes.

Notes are stored as ``.md`` files in a configurable directory (defaulting to
``~/.helix/notes/``).  Each note has a YAML-like header with the creation
timestamp and is named with a safe slug derived from the title.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from helix.tools.base import Tool

logger = logging.getLogger(__name__)

_NOTES_DIR = Path.home() / ".helix" / "notes"


def _slugify(text: str) -> str:
    """Convert a title to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:80] or "untitled"


class NoteTool(Tool):
    """Create, list, search, and read local Markdown notes."""

    @property
    def name(self) -> str:
        return "note"

    @property
    def description(self) -> str:
        return (
            "Manage local Markdown notes. "
            "Commands: 'create' (save a new note), 'list' (show all notes), "
            "'read' (open a note by title/filename), 'search' (find notes by keyword)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["create", "list", "read", "search"],
                    "description": "The action to perform.",
                },
                "title": {
                    "type": "string",
                    "description": "Note title (required for 'create' and 'read').",
                },
                "content": {
                    "type": "string",
                    "description": "Note body in Markdown (required for 'create').",
                },
                "query": {
                    "type": "string",
                    "description": "Search keyword (required for 'search').",
                },
            },
            "required": ["command"],
        }

    async def run(self, **kwargs: Any) -> str:
        """Dispatch to the appropriate sub-command."""
        command: str = kwargs.get("command", "")

        if command == "create":
            return self._create(kwargs)
        if command == "list":
            return self._list()
        if command == "read":
            return self._read(kwargs)
        if command == "search":
            return self._search(kwargs)

        return f"Error: unknown command '{command}'. Use 'create', 'list', 'read', or 'search'."

    def _create(self, kwargs: dict[str, Any]) -> str:
        title = kwargs.get("title")
        content = kwargs.get("content")
        if not title or not content:
            return "Error: 'title' and 'content' are required for 'create'."

        _NOTES_DIR.mkdir(parents=True, exist_ok=True)
        slug = _slugify(title)
        filepath = _NOTES_DIR / f"{slug}.md"

        now = datetime.now(UTC).isoformat()
        note_content = f"---\ntitle: {title}\ncreated: {now}\n---\n\n{content}\n"
        filepath.write_text(note_content, encoding="utf-8")

        logger.info("Note created", extra={"title": title, "path": str(filepath)})
        return f"Note saved: {filepath.name}"

    def _list(self) -> str:
        if not _NOTES_DIR.exists():
            return "No notes found."

        files = sorted(_NOTES_DIR.glob("*.md"))
        if not files:
            return "No notes found."

        lines = [f"**Notes ({len(files)})**\n"]
        for f in files:
            lines.append(f"- {f.stem}")
        return "\n".join(lines)

    def _read(self, kwargs: dict[str, Any]) -> str:
        title = kwargs.get("title")
        if not title:
            return "Error: 'title' is required for 'read'."

        slug = _slugify(title)
        filepath = _NOTES_DIR / f"{slug}.md"

        if not filepath.exists():
            # Try fuzzy match
            matches = list(_NOTES_DIR.glob(f"*{slug}*"))
            if matches:
                filepath = matches[0]
            else:
                return f"Note not found: {slug}"

        return filepath.read_text(encoding="utf-8")

    def _search(self, kwargs: dict[str, Any]) -> str:
        query = kwargs.get("query")
        if not query:
            return "Error: 'query' is required for 'search'."

        if not _NOTES_DIR.exists():
            return "No notes found."

        query_lower = query.lower()
        matches: list[str] = []
        for f in _NOTES_DIR.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            if query_lower in content.lower():
                matches.append(f.stem)

        if not matches:
            return f"No notes matching '{query}'."

        lines = [f"Found {len(matches)} note(s) matching '{query}':\n"]
        for m in matches:
            lines.append(f"- {m}")
        return "\n".join(lines)
