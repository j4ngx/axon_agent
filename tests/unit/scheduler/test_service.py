"""Tests for the ``SchedulerService``."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from helix.memory.models import Recurrence, Reminder
from helix.memory.reminder_repository import ReminderRepository
from helix.scheduler.service import SchedulerService


@pytest.fixture
def mock_repo() -> AsyncMock:
    return AsyncMock(spec=ReminderRepository)


@pytest.fixture
def mock_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def scheduler(mock_repo: AsyncMock, mock_bot: MagicMock) -> SchedulerService:
    return SchedulerService(reminder_repo=mock_repo, bot=mock_bot, check_interval=1.0)


class TestSchedulerService:
    """Unit tests for ``SchedulerService``."""

    async def test_when_no_due_reminders_expect_no_messages_sent(
        self,
        scheduler: SchedulerService,
        mock_repo: AsyncMock,
        mock_bot: MagicMock,
    ) -> None:
        mock_repo.get_due_reminders.return_value = []

        await scheduler.check_and_fire()

        mock_bot.send_message.assert_not_called()

    async def test_when_one_time_reminder_due_expect_message_and_completed(
        self,
        scheduler: SchedulerService,
        mock_repo: AsyncMock,
        mock_bot: MagicMock,
    ) -> None:
        reminder = Reminder(
            id="r1",
            user_id=42,
            message="Check PRs",
            trigger_at=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
            recurrence=None,
        )
        mock_repo.get_due_reminders.return_value = [reminder]

        await scheduler.check_and_fire()

        mock_bot.send_message.assert_called_once_with(
            chat_id=42,
            text="🔔 Reminder: Check PRs",
        )
        mock_repo.mark_completed.assert_called_once_with(42, "r1")
        mock_repo.update_next_trigger.assert_not_called()

    async def test_when_recurring_reminder_due_expect_message_and_rescheduled(
        self,
        scheduler: SchedulerService,
        mock_repo: AsyncMock,
        mock_bot: MagicMock,
    ) -> None:
        reminder = Reminder(
            id="r2",
            user_id=42,
            message="Daily standup",
            trigger_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            recurrence=Recurrence.DAILY,
        )
        mock_repo.get_due_reminders.return_value = [reminder]

        await scheduler.check_and_fire()

        mock_bot.send_message.assert_called_once()
        mock_repo.mark_completed.assert_not_called()
        mock_repo.update_next_trigger.assert_called_once_with(
            42,
            "r2",
            datetime(2026, 3, 2, 9, 0, tzinfo=UTC),
        )

    async def test_when_send_message_fails_expect_skipped_and_not_completed(
        self,
        scheduler: SchedulerService,
        mock_repo: AsyncMock,
        mock_bot: MagicMock,
    ) -> None:
        reminder = Reminder(
            id="r3",
            user_id=42,
            message="Oops",
            trigger_at=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
        )
        mock_repo.get_due_reminders.return_value = [reminder]
        mock_bot.send_message.side_effect = Exception("Telegram down")

        await scheduler.check_and_fire()

        mock_repo.mark_completed.assert_not_called()
        mock_repo.update_next_trigger.assert_not_called()

    async def test_when_multiple_due_expect_all_processed(
        self,
        scheduler: SchedulerService,
        mock_repo: AsyncMock,
        mock_bot: MagicMock,
    ) -> None:
        reminders = [
            Reminder(
                id="r4",
                user_id=42,
                message="One",
                trigger_at=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
            ),
            Reminder(
                id="r5",
                user_id=99,
                message="Two",
                trigger_at=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
                recurrence=Recurrence.WEEKLY,
            ),
        ]
        mock_repo.get_due_reminders.return_value = reminders

        await scheduler.check_and_fire()

        assert mock_bot.send_message.call_count == 2
        mock_repo.mark_completed.assert_called_once_with(42, "r4")
        mock_repo.update_next_trigger.assert_called_once_with(
            99,
            "r5",
            datetime(2026, 3, 8, 10, 0, tzinfo=UTC),
        )

    async def test_when_weekday_reminder_on_friday_expect_skip_weekend(
        self,
        scheduler: SchedulerService,
        mock_repo: AsyncMock,
        mock_bot: MagicMock,
    ) -> None:
        # 2026-03-06 is a Friday
        reminder = Reminder(
            id="r6",
            user_id=42,
            message="Weekday check",
            trigger_at=datetime(2026, 3, 6, 9, 0, tzinfo=UTC),
            recurrence=Recurrence.WEEKDAYS,
        )
        mock_repo.get_due_reminders.return_value = [reminder]

        await scheduler.check_and_fire()

        # Next trigger should be Monday 2026-03-09
        mock_repo.update_next_trigger.assert_called_once_with(
            42,
            "r6",
            datetime(2026, 3, 9, 9, 0, tzinfo=UTC),
        )

    async def test_when_monthly_reminder_expect_next_month(
        self,
        scheduler: SchedulerService,
        mock_repo: AsyncMock,
        mock_bot: MagicMock,
    ) -> None:
        reminder = Reminder(
            id="r7",
            user_id=42,
            message="Monthly review",
            trigger_at=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
            recurrence=Recurrence.MONTHLY,
        )
        mock_repo.get_due_reminders.return_value = [reminder]

        await scheduler.check_and_fire()

        mock_repo.update_next_trigger.assert_called_once_with(
            42,
            "r7",
            datetime(2026, 2, 15, 10, 0, tzinfo=UTC),
        )

    async def test_when_starting_twice_expect_single_task(
        self,
        scheduler: SchedulerService,
    ) -> None:
        scheduler.start()
        task1 = scheduler._task
        scheduler.start()
        task2 = scheduler._task

        assert task1 is task2
        await scheduler.stop()

    async def test_when_stopping_without_start_expect_no_error(
        self,
        scheduler: SchedulerService,
    ) -> None:
        await scheduler.stop()  # Should not raise
