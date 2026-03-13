"""Tests for the ``HabitRepository``."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from helix.memory.habit_repository import HabitRepository
from helix.memory.models import Habit


@pytest.fixture
def mock_firestore_for_habits():
    """Mock Firestore client modelling ``users/{uid}/habits/{hid}``."""
    mock_client = MagicMock()
    mock_users_coll = MagicMock()
    mock_user_doc = MagicMock()
    mock_habits_coll = MagicMock()

    mock_client.collection.return_value = mock_users_coll
    mock_users_coll.document.return_value = mock_user_doc
    mock_user_doc.collection.return_value = mock_habits_coll

    return mock_client, mock_habits_coll


class TestHabitRepository:
    """Unit tests for ``HabitRepository``."""

    async def test_when_creating_habit_expect_doc_set_called(
        self, mock_firestore_for_habits
    ) -> None:
        mock_client, mock_habits_coll = mock_firestore_for_habits
        mock_doc = MagicMock()
        mock_doc.id = "hab123"
        mock_doc.set = AsyncMock()
        mock_habits_coll.document.return_value = mock_doc

        repo = HabitRepository(mock_client)
        habit = Habit(user_id=42, name="Exercise")

        doc_id = await repo.create_habit(habit)

        assert doc_id == "hab123"
        mock_doc.set.assert_called_once_with(habit.to_dict())

    async def test_when_getting_active_habits_expect_query_built(
        self, mock_firestore_for_habits
    ) -> None:
        mock_client, mock_habits_coll = mock_firestore_for_habits

        mock_doc = MagicMock()
        mock_doc.id = "h1"
        mock_doc.to_dict.return_value = {
            "user_id": 42,
            "name": "Read",
            "frequency": "daily",
            "current_streak": 5,
            "best_streak": 10,
            "last_completed": "2026-03-01",
            "active": True,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        }

        mock_query = MagicMock()
        mock_query.order_by.return_value = mock_query
        mock_query.get = AsyncMock(return_value=[mock_doc])
        mock_habits_coll.where.return_value = mock_query

        repo = HabitRepository(mock_client)
        habits = await repo.get_active_habits(42)

        assert len(habits) == 1
        assert habits[0].name == "Read"
        assert habits[0].current_streak == 5
        mock_habits_coll.where.assert_called_once_with("active", "==", True)

    @freeze_time("2026-03-02 12:00:00", tz_offset=0)
    async def test_when_logging_completion_expect_streak_incremented(
        self, mock_firestore_for_habits
    ) -> None:
        mock_client, mock_habits_coll = mock_firestore_for_habits

        yesterday = date(2026, 3, 1)
        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = {
            "user_id": 42,
            "name": "Exercise",
            "frequency": "daily",
            "current_streak": 3,
            "best_streak": 5,
            "last_completed": yesterday.isoformat(),
            "active": True,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_doc_ref.update = AsyncMock()
        mock_habits_coll.document.return_value = mock_doc_ref

        repo = HabitRepository(mock_client)
        habit = await repo.log_completion(42, "h1")

        assert habit is not None
        assert habit.current_streak == 4
        mock_doc_ref.update.assert_called_once()

    async def test_when_logging_with_broken_streak_expect_reset_to_one(
        self, mock_firestore_for_habits
    ) -> None:
        mock_client, mock_habits_coll = mock_firestore_for_habits

        old_date = date(2026, 2, 1)  # Long ago
        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = {
            "user_id": 42,
            "name": "Exercise",
            "frequency": "daily",
            "current_streak": 10,
            "best_streak": 15,
            "last_completed": old_date.isoformat(),
            "active": True,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_doc_ref.update = AsyncMock()
        mock_habits_coll.document.return_value = mock_doc_ref

        repo = HabitRepository(mock_client)
        habit = await repo.log_completion(42, "h1")

        assert habit is not None
        assert habit.current_streak == 1

    async def test_when_logging_same_day_expect_no_double_count(
        self, mock_firestore_for_habits
    ) -> None:
        mock_client, mock_habits_coll = mock_firestore_for_habits

        today = datetime.now(UTC).date()
        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = {
            "user_id": 42,
            "name": "Exercise",
            "frequency": "daily",
            "current_streak": 5,
            "best_streak": 5,
            "last_completed": today.isoformat(),
            "active": True,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_doc_ref.update = AsyncMock()
        mock_habits_coll.document.return_value = mock_doc_ref

        repo = HabitRepository(mock_client)
        habit = await repo.log_completion(42, "h1")

        assert habit is not None
        assert habit.current_streak == 5  # Unchanged
        mock_doc_ref.update.assert_not_called()

    async def test_when_logging_nonexistent_habit_expect_none(
        self, mock_firestore_for_habits
    ) -> None:
        mock_client, mock_habits_coll = mock_firestore_for_habits

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_habits_coll.document.return_value = mock_doc_ref

        repo = HabitRepository(mock_client)
        result = await repo.log_completion(42, "nonexistent")

        assert result is None

    async def test_when_deactivating_existing_habit_expect_true(
        self, mock_firestore_for_habits
    ) -> None:
        mock_client, mock_habits_coll = mock_firestore_for_habits

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_doc_ref.update = AsyncMock()
        mock_habits_coll.document.return_value = mock_doc_ref

        repo = HabitRepository(mock_client)
        result = await repo.deactivate_habit(42, "h1")

        assert result is True
        mock_doc_ref.update.assert_called_once_with({"active": False})

    async def test_when_deactivating_nonexistent_habit_expect_false(
        self, mock_firestore_for_habits
    ) -> None:
        mock_client, mock_habits_coll = mock_firestore_for_habits

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_habits_coll.document.return_value = mock_doc_ref

        repo = HabitRepository(mock_client)
        result = await repo.deactivate_habit(42, "nonexistent")

        assert result is False

    @freeze_time("2026-03-02 12:00:00", tz_offset=0)
    async def test_when_logging_updates_best_streak_expect_new_best(
        self, mock_firestore_for_habits
    ) -> None:
        mock_client, mock_habits_coll = mock_firestore_for_habits

        yesterday = date(2026, 3, 1)
        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = {
            "user_id": 42,
            "name": "Meditate",
            "frequency": "daily",
            "current_streak": 5,
            "best_streak": 5,  # Same as current
            "last_completed": yesterday.isoformat(),
            "active": True,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_doc_ref.update = AsyncMock()
        mock_habits_coll.document.return_value = mock_doc_ref

        repo = HabitRepository(mock_client)
        habit = await repo.log_completion(42, "h1")

        assert habit is not None
        assert habit.current_streak == 6
        assert habit.best_streak == 6
