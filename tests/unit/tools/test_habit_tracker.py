"""Tests for the ``HabitTrackerTool``."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from helix.memory.habit_repository import HabitRepository
from helix.memory.models import Habit, HabitFrequency
from helix.tools.habit_tracker import HabitTrackerTool


@pytest.fixture
def mock_habit_repo() -> AsyncMock:
    return AsyncMock(spec=HabitRepository)


@pytest.fixture
def habit_tool(mock_habit_repo: AsyncMock) -> HabitTrackerTool:
    return HabitTrackerTool(repository=mock_habit_repo)


class TestHabitTrackerTool:
    """Unit tests for ``HabitTrackerTool``."""

    def test_when_checking_name_expect_habit_tracker(self, habit_tool: HabitTrackerTool) -> None:
        assert habit_tool.name == "habit_tracker"

    def test_when_checking_schema_expect_command_required(
        self, habit_tool: HabitTrackerTool
    ) -> None:
        schema = habit_tool.parameters_schema
        assert "command" in schema["properties"]
        assert schema["required"] == ["command"]

    async def test_when_no_user_id_expect_error(self, habit_tool: HabitTrackerTool) -> None:
        result = await habit_tool.run(command="list")
        assert "Error" in result

    async def test_when_creating_habit_expect_success(
        self,
        habit_tool: HabitTrackerTool,
        mock_habit_repo: AsyncMock,
    ) -> None:
        mock_habit_repo.create_habit.return_value = "hab123"

        result = await habit_tool.run(
            command="create",
            name="Exercise",
            _user_id=42,
        )

        assert "hab123" in result
        assert "Exercise" in result
        assert "daily" in result
        mock_habit_repo.create_habit.assert_called_once()

    async def test_when_creating_with_frequency_expect_correct_frequency(
        self,
        habit_tool: HabitTrackerTool,
        mock_habit_repo: AsyncMock,
    ) -> None:
        mock_habit_repo.create_habit.return_value = "w1"

        result = await habit_tool.run(
            command="create",
            name="Gym",
            frequency="weekly",
            _user_id=42,
        )

        assert "weekly" in result
        call_args = mock_habit_repo.create_habit.call_args[0][0]
        assert call_args.frequency == HabitFrequency.WEEKLY

    async def test_when_creating_without_name_expect_error(
        self, habit_tool: HabitTrackerTool
    ) -> None:
        result = await habit_tool.run(command="create", _user_id=42)
        assert "Error" in result
        assert "name" in result.lower()

    async def test_when_logging_habit_expect_streak_info(
        self,
        habit_tool: HabitTrackerTool,
        mock_habit_repo: AsyncMock,
    ) -> None:
        mock_habit_repo.log_completion.return_value = Habit(
            id="h1",
            user_id=42,
            name="Exercise",
            current_streak=5,
            best_streak=10,
        )

        result = await habit_tool.run(
            command="log",
            habit_id="h1",
            _user_id=42,
        )

        assert "Exercise" in result
        assert "5" in result  # current streak
        assert "10" in result  # best streak
        mock_habit_repo.log_completion.assert_called_once_with(42, "h1")

    async def test_when_logging_nonexistent_habit_expect_not_found(
        self,
        habit_tool: HabitTrackerTool,
        mock_habit_repo: AsyncMock,
    ) -> None:
        mock_habit_repo.log_completion.return_value = None

        result = await habit_tool.run(
            command="log",
            habit_id="nope",
            _user_id=42,
        )

        assert "not found" in result.lower()

    async def test_when_logging_without_id_expect_error(self, habit_tool: HabitTrackerTool) -> None:
        result = await habit_tool.run(command="log", _user_id=42)
        assert "Error" in result
        assert "habit_id" in result.lower()

    async def test_when_listing_habits_expect_formatted_output(
        self,
        habit_tool: HabitTrackerTool,
        mock_habit_repo: AsyncMock,
    ) -> None:
        mock_habit_repo.get_active_habits.return_value = [
            Habit(
                id="h1",
                user_id=42,
                name="Exercise",
                frequency=HabitFrequency.DAILY,
                current_streak=5,
                best_streak=10,
                last_completed=date(2026, 3, 1),
            ),
            Habit(
                id="h2",
                user_id=42,
                name="Read",
                frequency=HabitFrequency.DAILY,
                current_streak=3,
                best_streak=3,
            ),
        ]

        result = await habit_tool.run(command="list", _user_id=42)

        assert "2" in result
        assert "Exercise" in result
        assert "Read" in result
        assert "streak: 5" in result
        assert "best: 10" in result
        assert "2026-03-01" in result

    async def test_when_listing_empty_expect_no_habits_message(
        self,
        habit_tool: HabitTrackerTool,
        mock_habit_repo: AsyncMock,
    ) -> None:
        mock_habit_repo.get_active_habits.return_value = []

        result = await habit_tool.run(command="list", _user_id=42)

        assert "no active" in result.lower()

    async def test_when_deactivating_existing_expect_success(
        self,
        habit_tool: HabitTrackerTool,
        mock_habit_repo: AsyncMock,
    ) -> None:
        mock_habit_repo.deactivate_habit.return_value = True

        result = await habit_tool.run(
            command="deactivate",
            habit_id="h1",
            _user_id=42,
        )

        assert "deactivated" in result.lower()
        mock_habit_repo.deactivate_habit.assert_called_once_with(42, "h1")

    async def test_when_deactivating_nonexistent_expect_not_found(
        self,
        habit_tool: HabitTrackerTool,
        mock_habit_repo: AsyncMock,
    ) -> None:
        mock_habit_repo.deactivate_habit.return_value = False

        result = await habit_tool.run(
            command="deactivate",
            habit_id="nope",
            _user_id=42,
        )

        assert "not found" in result.lower()

    async def test_when_deactivating_without_id_expect_error(
        self, habit_tool: HabitTrackerTool
    ) -> None:
        result = await habit_tool.run(command="deactivate", _user_id=42)
        assert "Error" in result
        assert "habit_id" in result.lower()

    async def test_when_unknown_command_expect_error(self, habit_tool: HabitTrackerTool) -> None:
        result = await habit_tool.run(command="fly", _user_id=42)
        assert "Error" in result
        assert "unknown command" in result.lower()
