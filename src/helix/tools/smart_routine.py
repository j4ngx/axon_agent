"""Built-in tool: smart_routine — create and manage conditional automations.

Routines are evaluated periodically by the scheduler.  This tool
provides CRUD operations for the user to define their routines via chat.
"""

from __future__ import annotations

import logging
from typing import Any

from helix.memory.models import ConditionType, Routine
from helix.memory.routine_repository import RoutineRepository
from helix.tools.base import Tool

logger = logging.getLogger(__name__)

_CONDITION_DESCRIPTIONS = {
    "habit_not_logged_by": (
        "Fire if a habit hasn't been logged by a certain time. "
        "Params: habit_name, check_time (HH:MM)."
    ),
    "no_todo_completed_today": ("Fire if no todo was completed today. Params: check_time (HH:MM)."),
    "daily_briefing": ("Send a daily briefing at a specific time. Params: send_time (HH:MM)."),
    "custom_reminder": (
        "Send a custom message at a specific time. Params: send_time (HH:MM), message."
    ),
}


class SmartRoutineTool(Tool):
    """Create, list, toggle, and delete smart routines (conditional automations)."""

    def __init__(self, repository: RoutineRepository) -> None:
        self._repo = repository

    @property
    def name(self) -> str:
        return "smart_routine"

    @property
    def description(self) -> str:
        return (
            "Manage smart routines — conditional automations that trigger based on rules. "
            "Commands: 'create' (define a new routine), "
            "'list' (show all routines), "
            "'toggle' (enable/disable a routine), "
            "'delete' (remove a routine). "
            "Condition types: habit_not_logged_by, no_todo_completed_today, "
            "daily_briefing, custom_reminder."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["create", "list", "toggle", "delete"],
                    "description": "The action to perform.",
                },
                "name": {
                    "type": "string",
                    "description": "Routine name (required for 'create').",
                },
                "condition_type": {
                    "type": "string",
                    "enum": [
                        "habit_not_logged_by",
                        "no_todo_completed_today",
                        "daily_briefing",
                        "custom_reminder",
                    ],
                    "description": "Type of condition (required for 'create').",
                },
                "condition_params": {
                    "type": "object",
                    "description": (
                        "Parameters for the condition. "
                        'E.g. {"habit_name": "Exercise", "check_time": "21:00"} '
                        'or {"send_time": "08:00"}.'
                    ),
                },
                "action_message": {
                    "type": "string",
                    "description": (
                        "Message to send when the condition fires (required for 'create')."
                    ),
                },
                "routine_id": {
                    "type": "string",
                    "description": "Routine ID (required for 'toggle' and 'delete').",
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

        if command == "create":
            return await self._create(user_id, kwargs)
        if command == "list":
            return await self._list(user_id)
        if command == "toggle":
            return await self._toggle(user_id, kwargs)
        if command == "delete":
            return await self._delete(user_id, kwargs)

        return f"Error: unknown command '{command}'. Use 'create', 'list', 'toggle', or 'delete'."

    async def _create(self, user_id: int, kwargs: dict[str, Any]) -> str:
        """Create a new routine."""
        name = kwargs.get("name", "").strip()
        if not name:
            return "Error: 'name' is required."

        condition_type_str = kwargs.get("condition_type", "").strip()
        if not condition_type_str:
            return "Error: 'condition_type' is required. Options: " + ", ".join(
                _CONDITION_DESCRIPTIONS.keys()
            )

        try:
            condition_type = ConditionType(condition_type_str)
        except ValueError:
            return f"Error: unknown condition type '{condition_type_str}'. Options: " + ", ".join(
                _CONDITION_DESCRIPTIONS.keys()
            )

        action_message = kwargs.get("action_message", "").strip()
        if not action_message:
            return "Error: 'action_message' is required."

        condition_params = kwargs.get("condition_params", {})

        routine = Routine(
            user_id=user_id,
            name=name,
            condition_type=condition_type,
            condition_params=condition_params,
            action_message=action_message,
        )

        doc_id = await self._repo.create(routine)
        return (
            f"✅ Routine **{name}** created (ID: `{doc_id}`).\n"
            f"Condition: {_CONDITION_DESCRIPTIONS.get(condition_type_str, condition_type_str)}"
        )

    async def _list(self, user_id: int) -> str:
        """List all routines."""
        routines = await self._repo.get_all(user_id)
        if not routines:
            return "No routines configured. Use 'create' to set one up."

        lines = ["⚙️ **Smart Routines**:"]
        for r in routines:
            status = "✅" if r.active else "⏸️"
            lines.append(f"  {status} `{r.id}` — **{r.name}** ({r.condition_type.value})")

        return "\n".join(lines)

    async def _toggle(self, user_id: int, kwargs: dict[str, Any]) -> str:
        """Toggle a routine on/off."""
        routine_id = kwargs.get("routine_id", "").strip()
        if not routine_id:
            return "Error: 'routine_id' is required. Use 'list' to see your routines."

        new_state = await self._repo.toggle(user_id, routine_id)
        if new_state is None:
            return f"Routine `{routine_id}` not found."

        label = "enabled" if new_state else "disabled"
        return f"✅ Routine `{routine_id}` is now **{label}**."

    async def _delete(self, user_id: int, kwargs: dict[str, Any]) -> str:
        """Delete a routine."""
        routine_id = kwargs.get("routine_id", "").strip()
        if not routine_id:
            return "Error: 'routine_id' is required. Use 'list' to see your routines."

        deleted = await self._repo.delete(user_id, routine_id)
        if not deleted:
            return f"Routine `{routine_id}` not found."
        return f"✅ Routine `{routine_id}` deleted."
