"""Built-in tool: reminder — create, list, and cancel scheduled reminders.

The LLM calls this tool with a ``command`` argument (``create``, ``list``, or
``cancel``) and the appropriate parameters.  The ``_user_id`` keyword is
injected automatically by the agent loop and is **not** declared in the
parameters schema (the LLM never sees it).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from helix.memory.models import Recurrence, Reminder
from helix.memory.reminder_repository import ReminderRepository
from helix.tools.base import Tool

logger = logging.getLogger(__name__)


class ReminderTool(Tool):
    """Create, list, and cancel scheduled reminders."""

    def __init__(self, repository: ReminderRepository) -> None:
        self._repo = repository

    @property
    def name(self) -> str:
        return "reminder"

    @property
    def description(self) -> str:
        return (
            "Manage reminders and scheduled tasks. "
            "Commands: 'create' (schedule a new reminder), "
            "'list' (show pending reminders), "
            "'cancel' (cancel a reminder by ID)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["create", "list", "cancel"],
                    "description": "The action to perform.",
                },
                "message": {
                    "type": "string",
                    "description": "Reminder text (required for 'create').",
                },
                "trigger_at": {
                    "type": "string",
                    "description": (
                        "ISO-8601 datetime for when the reminder should fire "
                        "(required for 'create'). Must be in UTC."
                    ),
                },
                "recurrence": {
                    "type": "string",
                    "enum": ["daily", "weekdays", "weekly", "monthly"],
                    "description": "Optional recurrence pattern for 'create'.",
                },
                "reminder_id": {
                    "type": "string",
                    "description": "Reminder ID (required for 'cancel').",
                },
            },
            "required": ["command"],
        }

    async def run(self, **kwargs: Any) -> str:
        """Dispatch to the appropriate sub-command.

        The ``_user_id`` keyword is injected by the agent loop.
        """
        command = kwargs.get("command", "")
        user_id: int = kwargs.get("_user_id", 0)

        if not user_id:
            return "Error: could not determine user identity."

        if command == "create":
            return await self._create(user_id, kwargs)
        if command == "list":
            return await self._list(user_id)
        if command == "cancel":
            return await self._cancel(user_id, kwargs)

        return f"Error: unknown command '{command}'. Use 'create', 'list', or 'cancel'."

    async def _create(self, user_id: int, kwargs: dict[str, Any]) -> str:
        message = kwargs.get("message")
        trigger_at_str = kwargs.get("trigger_at")

        if not message:
            return "Error: 'message' is required for creating a reminder."
        if not trigger_at_str:
            return "Error: 'trigger_at' is required for creating a reminder."

        try:
            trigger_at = datetime.fromisoformat(trigger_at_str)
            # Ensure UTC
            if trigger_at.tzinfo is None:
                trigger_at = trigger_at.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            return f"Error: invalid datetime format '{trigger_at_str}'. Use ISO-8601."

        if trigger_at <= datetime.now(UTC):
            return "Error: 'trigger_at' must be in the future."

        recurrence_str = kwargs.get("recurrence")
        recurrence = Recurrence(recurrence_str) if recurrence_str else None

        reminder = Reminder(
            user_id=user_id,
            message=message,
            trigger_at=trigger_at,
            recurrence=recurrence,
        )
        doc_id = await self._repo.create_reminder(reminder)

        recurrence_text = f" (repeats {recurrence.value})" if recurrence else ""
        return (
            f"Reminder created (ID: {doc_id}). "
            f"Scheduled for {trigger_at.isoformat()}{recurrence_text}."
        )

    async def _list(self, user_id: int) -> str:
        reminders = await self._repo.get_pending_reminders(user_id)
        if not reminders:
            return "You have no pending reminders."

        lines = []
        for r in reminders:
            recurrence_text = f" [{r.recurrence.value}]" if r.recurrence else ""
            lines.append(f"- **{r.id}**: {r.message} — {r.trigger_at.isoformat()}{recurrence_text}")
        return f"Pending reminders ({len(reminders)}):\n" + "\n".join(lines)

    async def _cancel(self, user_id: int, kwargs: dict[str, Any]) -> str:
        reminder_id = kwargs.get("reminder_id")
        if not reminder_id:
            return "Error: 'reminder_id' is required for cancelling a reminder."

        cancelled = await self._repo.cancel_reminder(user_id, reminder_id)
        if cancelled:
            return f"Reminder {reminder_id} has been cancelled."
        return f"Reminder {reminder_id} not found or already completed."
