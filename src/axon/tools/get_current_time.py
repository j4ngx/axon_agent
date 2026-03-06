"""Built-in tool: get_current_time.

Returns the current system date/time in both ISO 8601 and human-readable
formats so the LLM can answer time-related questions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from axon.tools.base import Tool


class GetCurrentTimeTool(Tool):
    """Report the current UTC date and time."""

    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return (
            "Returns the current date and time in UTC. "
            "Use this when the user asks for the current time or date."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def run(self, **kwargs: Any) -> str:
        """Return the current UTC time.

        Returns:
            A string containing both ISO 8601 and human-readable representations.
        """
        now = datetime.now(UTC)
        iso = now.isoformat()
        human = now.strftime("%A, %B %d, %Y at %H:%M:%S UTC")
        return f"{iso} ({human})"
