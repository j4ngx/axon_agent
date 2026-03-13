"""Built-in tool: habit_tracker — create, track, and review habits.

The LLM calls this tool with a ``command`` argument and the appropriate
parameters.  The ``_user_id`` keyword is injected automatically by the
agent loop and is **not** declared in the parameters schema.
"""

from __future__ import annotations

import logging
from typing import Any

from helix.memory.habit_repository import HabitRepository
from helix.memory.models import Habit, HabitFrequency
from helix.tools.base import Tool

logger = logging.getLogger(__name__)


class HabitTrackerTool(Tool):
    """Create, track, and review personal habits with streaks."""

    def __init__(self, repository: HabitRepository) -> None:
        self._repo = repository

    @property
    def name(self) -> str:
        return "habit_tracker"

    @property
    def description(self) -> str:
        return (
            "Track daily habits and streaks. "
            "Commands: 'create' (start tracking a new habit), "
            "'log' (record today's completion), "
            "'list' (show active habits with streaks), "
            "'deactivate' (stop tracking a habit)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["create", "log", "list", "deactivate"],
                    "description": "The action to perform.",
                },
                "name": {
                    "type": "string",
                    "description": "Habit name (required for 'create').",
                },
                "frequency": {
                    "type": "string",
                    "enum": ["daily", "weekdays", "weekly"],
                    "description": "Expected frequency (default: daily).",
                },
                "habit_id": {
                    "type": "string",
                    "description": "Habit ID (required for 'log' and 'deactivate').",
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
        if command == "log":
            return await self._log(user_id, kwargs)
        if command == "list":
            return await self._list(user_id)
        if command == "deactivate":
            return await self._deactivate(user_id, kwargs)

        return f"Error: unknown command '{command}'. Use 'create', 'log', 'list', or 'deactivate'."

    async def _create(self, user_id: int, kwargs: dict[str, Any]) -> str:
        name = kwargs.get("name")
        if not name:
            return "Error: 'name' is required for creating a habit."

        frequency = HabitFrequency(kwargs.get("frequency", "daily"))

        habit = Habit(
            user_id=user_id,
            name=name,
            frequency=frequency,
        )
        doc_id = await self._repo.create_habit(habit)
        return f"Habit created (ID: {doc_id}): {name} [{frequency.value}]"

    async def _log(self, user_id: int, kwargs: dict[str, Any]) -> str:
        habit_id = kwargs.get("habit_id")
        if not habit_id:
            return "Error: 'habit_id' is required for logging a habit."

        habit = await self._repo.log_completion(user_id, habit_id)
        if not habit:
            return f"Habit {habit_id} not found."

        return (
            f"Logged '{habit.name}' — "
            f"current streak: {habit.current_streak} | "
            f"best streak: {habit.best_streak}"
        )

    async def _list(self, user_id: int) -> str:
        habits = await self._repo.get_active_habits(user_id)
        if not habits:
            return "You have no active habits."

        lines = []
        for h in habits:
            streak_info = f"streak: {h.current_streak}"
            if h.best_streak > h.current_streak:
                streak_info += f" (best: {h.best_streak})"
            last = f" | last: {h.last_completed.isoformat()}" if h.last_completed else ""
            lines.append(f"- **{h.id}**: {h.name} [{h.frequency.value}] — {streak_info}{last}")
        return f"Active habits ({len(habits)}):\n" + "\n".join(lines)

    async def _deactivate(self, user_id: int, kwargs: dict[str, Any]) -> str:
        habit_id = kwargs.get("habit_id")
        if not habit_id:
            return "Error: 'habit_id' is required for deactivating a habit."

        deactivated = await self._repo.deactivate_habit(user_id, habit_id)
        if deactivated:
            return f"Habit {habit_id} has been deactivated."
        return f"Habit {habit_id} not found."
