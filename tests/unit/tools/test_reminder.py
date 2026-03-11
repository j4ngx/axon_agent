"""Tests for the ``ReminderTool``."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from freezegun import freeze_time

from helix.memory.models import Recurrence, Reminder
from helix.memory.reminder_repository import ReminderRepository
from helix.tools.reminder import ReminderTool


@pytest.fixture
def mock_reminder_repo() -> AsyncMock:
    return AsyncMock(spec=ReminderRepository)


@pytest.fixture
def reminder_tool(mock_reminder_repo: AsyncMock) -> ReminderTool:
    return ReminderTool(repository=mock_reminder_repo)


class TestReminderTool:
    """Unit tests for ``ReminderTool``."""

    def test_when_checking_name_expect_reminder(self, reminder_tool: ReminderTool) -> None:
        assert reminder_tool.name == "reminder"

    def test_when_checking_schema_expect_command_required(
        self, reminder_tool: ReminderTool
    ) -> None:
        schema = reminder_tool.parameters_schema
        assert "command" in schema["properties"]
        assert schema["required"] == ["command"]

    async def test_when_no_user_id_expect_error(self, reminder_tool: ReminderTool) -> None:
        result = await reminder_tool.run(command="list")
        assert "Error" in result

    @freeze_time("2026-03-01 10:00:00", tz_offset=0)
    async def test_when_creating_reminder_expect_success(
        self,
        reminder_tool: ReminderTool,
        mock_reminder_repo: AsyncMock,
    ) -> None:
        mock_reminder_repo.create_reminder.return_value = "abc123"

        result = await reminder_tool.run(
            command="create",
            message="Check PRs",
            trigger_at="2026-06-01T12:00:00+00:00",
            _user_id=42,
        )

        assert "abc123" in result
        assert "Reminder created" in result
        mock_reminder_repo.create_reminder.assert_called_once()

    @freeze_time("2026-03-01 10:00:00", tz_offset=0)
    async def test_when_creating_with_recurrence_expect_recurrence_in_response(
        self,
        reminder_tool: ReminderTool,
        mock_reminder_repo: AsyncMock,
    ) -> None:
        mock_reminder_repo.create_reminder.return_value = "rec123"

        result = await reminder_tool.run(
            command="create",
            message="Daily standup",
            trigger_at="2026-06-01T09:00:00+00:00",
            recurrence="daily",
            _user_id=42,
        )

        assert "repeats daily" in result
        call_args = mock_reminder_repo.create_reminder.call_args[0][0]
        assert call_args.recurrence == Recurrence.DAILY

    async def test_when_creating_without_message_expect_error(
        self, reminder_tool: ReminderTool
    ) -> None:
        result = await reminder_tool.run(
            command="create",
            trigger_at="2026-06-01T12:00:00+00:00",
            _user_id=42,
        )
        assert "Error" in result
        assert "message" in result.lower()

    async def test_when_creating_without_trigger_at_expect_error(
        self, reminder_tool: ReminderTool
    ) -> None:
        result = await reminder_tool.run(
            command="create",
            message="Test",
            _user_id=42,
        )
        assert "Error" in result
        assert "trigger_at" in result.lower()

    @freeze_time("2026-06-02 10:00:00", tz_offset=0)
    async def test_when_creating_with_past_trigger_expect_error(
        self, reminder_tool: ReminderTool
    ) -> None:
        result = await reminder_tool.run(
            command="create",
            message="Too late",
            trigger_at="2026-06-01T12:00:00+00:00",
            _user_id=42,
        )
        assert "Error" in result
        assert "future" in result.lower()

    async def test_when_creating_with_invalid_datetime_expect_error(
        self, reminder_tool: ReminderTool
    ) -> None:
        result = await reminder_tool.run(
            command="create",
            message="Test",
            trigger_at="not-a-date",
            _user_id=42,
        )
        assert "Error" in result
        assert "ISO-8601" in result

    async def test_when_listing_reminders_expect_formatted_output(
        self,
        reminder_tool: ReminderTool,
        mock_reminder_repo: AsyncMock,
    ) -> None:
        mock_reminder_repo.get_pending_reminders.return_value = [
            Reminder(
                id="r1",
                user_id=42,
                message="Check PRs",
                trigger_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
            ),
            Reminder(
                id="r2",
                user_id=42,
                message="Meeting",
                trigger_at=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
                recurrence=Recurrence.WEEKLY,
            ),
        ]

        result = await reminder_tool.run(command="list", _user_id=42)

        assert "2" in result
        assert "Check PRs" in result
        assert "Meeting" in result
        assert "[weekly]" in result

    async def test_when_listing_empty_expect_no_reminders_message(
        self,
        reminder_tool: ReminderTool,
        mock_reminder_repo: AsyncMock,
    ) -> None:
        mock_reminder_repo.get_pending_reminders.return_value = []

        result = await reminder_tool.run(command="list", _user_id=42)

        assert "no pending" in result.lower()

    async def test_when_cancelling_existing_expect_success(
        self,
        reminder_tool: ReminderTool,
        mock_reminder_repo: AsyncMock,
    ) -> None:
        mock_reminder_repo.cancel_reminder.return_value = True

        result = await reminder_tool.run(
            command="cancel",
            reminder_id="r1",
            _user_id=42,
        )

        assert "cancelled" in result.lower()
        mock_reminder_repo.cancel_reminder.assert_called_once_with(42, "r1")

    async def test_when_cancelling_nonexistent_expect_not_found(
        self,
        reminder_tool: ReminderTool,
        mock_reminder_repo: AsyncMock,
    ) -> None:
        mock_reminder_repo.cancel_reminder.return_value = False

        result = await reminder_tool.run(
            command="cancel",
            reminder_id="nope",
            _user_id=42,
        )

        assert "not found" in result.lower()

    async def test_when_cancelling_without_id_expect_error(
        self, reminder_tool: ReminderTool
    ) -> None:
        result = await reminder_tool.run(command="cancel", _user_id=42)
        assert "Error" in result

    async def test_when_unknown_command_expect_error(self, reminder_tool: ReminderTool) -> None:
        result = await reminder_tool.run(command="destroy", _user_id=42)
        assert "Error" in result
        assert "unknown command" in result.lower()
