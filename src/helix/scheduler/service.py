"""Background scheduler for firing due reminders.

Runs as an ``asyncio.Task`` alongside the Telegram long-polling loop.
Every ``check_interval`` seconds it queries Firestore for pending reminders
whose ``trigger_at`` has passed, sends a Telegram notification, and either
marks them completed (one-time) or reschedules them (recurring).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from helix.memory.reminder_repository import ReminderRepository

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)


class SchedulerService:
    """Periodically checks for and fires due reminders.

    Args:
        reminder_repo: The reminder repository.
        bot: The Telegram bot (used to send notifications).
        check_interval: Seconds between each check cycle.
    """

    def __init__(
        self,
        reminder_repo: ReminderRepository,
        bot: Bot,
        check_interval: float = 30.0,
    ) -> None:
        self._repo = reminder_repo
        self._bot = bot
        self._interval = check_interval
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
