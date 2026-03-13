"""Background scheduler for firing due reminders and evaluating routines.

Runs as an ``asyncio.Task`` alongside the Telegram long-polling loop.
Every ``check_interval`` seconds it queries Firestore for pending reminders
whose ``trigger_at`` has passed, sends a Telegram notification, and either
marks them completed (one-time) or reschedules them (recurring).

Additionally checks smart routines and fires them when conditions are met.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from helix.memory.models import ConditionType
from helix.memory.reminder_repository import ReminderRepository

if TYPE_CHECKING:
    from aiogram import Bot

    from helix.memory.habit_repository import HabitRepository
    from helix.memory.models import Routine
    from helix.memory.routine_repository import RoutineRepository
    from helix.memory.todo_repository import TodoRepository

logger = logging.getLogger(__name__)


class SchedulerService:
    """Periodically checks for and fires due reminders and routines.

    Args:
        reminder_repo: The reminder repository.
        bot: The Telegram bot (used to send notifications).
        check_interval: Seconds between each check cycle.
        routine_repo: Optional routine repository for smart routines.
        todo_repo: Optional todo repository (for routine conditions).
        habit_repo: Optional habit repository (for routine conditions).
    """

    def __init__(
        self,
        reminder_repo: ReminderRepository,
        bot: Bot,
        check_interval: float = 30.0,
        routine_repo: RoutineRepository | None = None,
        todo_repo: TodoRepository | None = None,
        habit_repo: HabitRepository | None = None,
    ) -> None:
        self._repo = reminder_repo
        self._bot = bot
        self._interval = check_interval
        self._routine_repo = routine_repo
        self._todo_repo = todo_repo
        self._habit_repo = habit_repo
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Launch the background check loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "Scheduler started",
            extra={"check_interval": self._interval},
        )

    async def stop(self) -> None:
        """Cancel the background task and wait for it to finish."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        """Infinite loop: sleep → check → fire."""
        while True:
            try:
                await asyncio.sleep(self._interval)
                await self.check_and_fire()
                await self.check_routines()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scheduler tick failed")

    async def check_and_fire(self) -> None:
        """Query due reminders and deliver them.

        This method is public so tests can call it directly without
        running the background loop.
        """
        due = await self._repo.get_due_reminders()
        if not due:
            return

        logger.info("Due reminders found", extra={"count": len(due)})

        for reminder in due:
            try:
                await self._bot.send_message(
                    chat_id=reminder.user_id,
                    text=f"🔔 Reminder: {reminder.message}",
                )
                logger.info(
                    "Reminder delivered",
                    extra={
                        "user_id": reminder.user_id,
                        "reminder_id": reminder.id,
                    },
                )
            except Exception:
                logger.exception(
                    "Failed to send reminder",
                    extra={
                        "user_id": reminder.user_id,
                        "reminder_id": reminder.id,
                    },
                )
                continue

            # Handle completion / recurrence.
            assert reminder.id is not None
            next_trigger = reminder.compute_next_trigger()
            if next_trigger is None:
                await self._repo.mark_completed(reminder.user_id, reminder.id)
            else:
                await self._repo.update_next_trigger(reminder.user_id, reminder.id, next_trigger)

    async def check_routines(self) -> None:
        """Evaluate active routines and fire those whose conditions are met.

        This method is public so tests can call it directly.
        """
        if self._routine_repo is None:
            return

        # We need to check routines per user.  Since this is a personal bot
        # with very few users, we iterate over all active routines globally.
        # In a production multi-user system, this would be batched differently.
        all_routines = []
        try:
            # Firestore needs per-user queries; for a single-user bot we use
            # a simple approach: get root "users" collection and iterate.
            users_ref = self._routine_repo._client.collection("users")
            async for user_doc in users_ref.list_documents():
                user_id = int(user_doc.id)
                routines = await self._routine_repo.get_active(user_id)
                for r in routines:
                    all_routines.append((user_id, r))
        except Exception:
            logger.exception("Failed to fetch routines")
            return

        if not all_routines:
            return

        now = datetime.now(UTC)
        today = now.date()

        for user_id, routine in all_routines:
            try:
                # Skip if already triggered today
                if routine.last_triggered and routine.last_triggered.date() == today:
                    continue

                should_fire = await self._evaluate_condition(routine, user_id, now, today)
                if not should_fire:
                    continue

                await self._bot.send_message(
                    chat_id=user_id,
                    text=f"⚙️ Routine **{routine.name}**: {routine.action_message}",
                    parse_mode="Markdown",
                )
                if routine.id:
                    await self._routine_repo.update_last_triggered(user_id, routine.id)

                logger.info(
                    "Routine fired",
                    extra={"user_id": user_id, "routine_id": routine.id, "name": routine.name},
                )
            except Exception:
                logger.exception(
                    "Failed to evaluate routine",
                    extra={"user_id": user_id, "routine_id": routine.id},
                )

    async def _evaluate_condition(
        self,
        routine: Routine,
        user_id: int,
        now: datetime,
        today: date,
    ) -> bool:
        """Check if a routine's condition is met right now."""

        params = routine.condition_params
        check_time_str = params.get("check_time") or params.get("send_time", "")

        # Parse check_time if present
        if check_time_str:
            try:
                hour, minute = map(int, check_time_str.split(":"))
                # Only fire within the check window (check_interval * 2 seconds around the time)
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                diff = abs((now - target).total_seconds())
                if diff > self._interval * 2:
                    return False
            except (ValueError, TypeError):
                pass

        if routine.condition_type == ConditionType.DAILY_BRIEFING:
            return True  # Time check above is sufficient

        if routine.condition_type == ConditionType.CUSTOM_REMINDER:
            return True  # Time check above is sufficient

        if routine.condition_type == ConditionType.HABIT_NOT_LOGGED_BY:
            if self._habit_repo is None:
                return False
            habit_name = params.get("habit_name", "")
            habits = await self._habit_repo.get_habits(user_id)
            for h in habits:
                if h.name.lower() == habit_name.lower() and (
                    h.last_completed is None or h.last_completed < today
                ):
                    return True
            return False

        if routine.condition_type == ConditionType.NO_TODO_COMPLETED_TODAY:
            if self._todo_repo is None:
                return False
            completed = await self._todo_repo.get_todos(user_id, status="completed")
            # Check if any were completed today
            return all(not (t.completed_at and t.completed_at.date() == today) for t in completed)

        return False
