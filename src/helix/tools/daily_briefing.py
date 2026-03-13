"""Built-in tool: daily_briefing — aggregated daily summary.

Gathers weather, pending todos, habit streaks, and upcoming reminders
into a single on-demand briefing.  The ``_user_id`` keyword is injected
automatically by the agent loop.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from helix.config.settings import Settings
from helix.memory.habit_repository import HabitRepository
from helix.memory.reminder_repository import ReminderRepository
from helix.memory.todo_repository import TodoRepository
from helix.tools.base import Tool
from helix.tools.weather import fetch_weather

logger = logging.getLogger(__name__)


class DailyBriefingTool(Tool):
    """Generate an on-demand daily briefing with weather, tasks, habits, and reminders."""

    def __init__(
        self,
        todo_repo: TodoRepository,
        habit_repo: HabitRepository,
        reminder_repo: ReminderRepository,
        settings: Settings,
    ) -> None:
        self._todo_repo = todo_repo
        self._habit_repo = habit_repo
        self._reminder_repo = reminder_repo
        self._settings = settings

    @property
    def name(self) -> str:
        return "daily_briefing"

    @property
    def description(self) -> str:
        return (
            "Generate a daily briefing with current weather, pending tasks, "
            "habit streaks, and upcoming reminders. Call with no arguments "
            "for the full briefing, or pass 'sections' to include only specific parts."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["weather", "todos", "habits", "reminders"],
                    },
                    "description": ("Optional list of sections to include. Omit for all sections."),
                },
            },
        }

    async def run(self, **kwargs: Any) -> str:
        """Build and return the daily briefing."""
        user_id: int = kwargs.get("_user_id", 0)
        if not user_id:
            return "Error: could not determine user identity."

        sections = kwargs.get("sections") or ["weather", "todos", "habits", "reminders"]
        parts: list[str] = ["📋 **Daily Briefing**\n"]

        if "weather" in sections:
            parts.append(await self._weather_section())

        if "todos" in sections:
            parts.append(await self._todos_section(user_id))

        if "habits" in sections:
            parts.append(await self._habits_section(user_id))

        if "reminders" in sections:
            parts.append(await self._reminders_section(user_id))

        return "\n".join(parts)

    async def _weather_section(self) -> str:
        """Fetch weather for the configured location."""
        weather_cfg = getattr(self._settings, "weather", None)
        lat = getattr(weather_cfg, "latitude", 37.1773) if weather_cfg else 37.1773
        lon = getattr(weather_cfg, "longitude", -3.5986) if weather_cfg else -3.5986
        location = getattr(weather_cfg, "location_name", "Granada") if weather_cfg else "Granada"

        data = await fetch_weather(lat, lon)
        if "error" in data:
            return f"🌤️ **Weather** ({location}): unavailable — {data['error']}"

        temp = data.get("temperature", "?")
        desc = data.get("description", "Unknown")
        wind = data.get("wind_speed", "?")
        humidity = data.get("humidity", "?")

        return (
            f"🌤️ **Weather** ({location}): {desc}, {temp}°C, wind {wind} km/h, humidity {humidity}%"
        )

    async def _todos_section(self, user_id: int) -> str:
        """List top 5 pending todos."""
        todos = await self._todo_repo.get_todos(user_id, status="pending")
        if not todos:
            return "✅ **Tasks**: No pending tasks — great job!"

        lines = ["📝 **Pending Tasks**:"]
        for t in todos[:5]:
            priority_emoji = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                t.priority.value, "⚪"
            )
            due = f" (due {t.due_date})" if t.due_date else ""
            lines.append(f"  {priority_emoji} {t.title}{due}")

        remaining = len(todos) - 5
        if remaining > 0:
            lines.append(f"  … and {remaining} more")

        return "\n".join(lines)

    async def _habits_section(self, user_id: int) -> str:
        """Show active habits with streak info."""
        habits = await self._habit_repo.get_active_habits(user_id)
        if not habits:
            return "💪 **Habits**: No habits tracked yet."

        lines = ["💪 **Habit Streaks**:"]
        for h in habits:
            alive = "🔥" if h.check_streak() else "❄️"
            lines.append(f"  {alive} {h.name}: {h.current_streak} day streak")

        return "\n".join(lines)

    async def _reminders_section(self, user_id: int) -> str:
        """Show reminders due in the next 24 hours."""
        now = datetime.now(UTC)
        cutoff = now + timedelta(hours=24)

        all_reminders = await self._reminder_repo.get_pending_reminders(user_id)
        upcoming = [r for r in all_reminders if r.trigger_at <= cutoff]

        if not upcoming:
            return "🔔 **Reminders**: Nothing in the next 24 hours."

        lines = ["🔔 **Upcoming Reminders**:"]
        for r in upcoming:
            time_str = r.trigger_at.strftime("%H:%M")
            lines.append(f"  ⏰ {time_str} — {r.message}")

        return "\n".join(lines)
