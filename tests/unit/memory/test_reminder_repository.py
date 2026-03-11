"""Tests for the ``ReminderRepository``."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from helix.memory.models import Recurrence, Reminder
from helix.memory.reminder_repository import ReminderRepository


@pytest.fixture
def mock_firestore_for_reminders():
    """Mock Firestore client modelling ``users/{uid}/reminders/{rid}``."""
    mock_client = MagicMock()
    mock_users_coll = MagicMock()
    mock_user_doc = MagicMock()
    mock_reminders_coll = MagicMock()

    mock_client.collection.return_value = mock_users_coll
    mock_users_coll.document.return_value = mock_user_doc
    mock_user_doc.collection.return_value = mock_reminders_coll

    return mock_client, mock_reminders_coll


class TestReminderRepository:
    """Unit tests for ``ReminderRepository``."""

    async def test_when_creating_reminder_expect_doc_set_called(
        self, mock_firestore_for_reminders
    ) -> None:
        mock_client, mock_reminders_coll = mock_firestore_for_reminders
        mock_doc = MagicMock()
        mock_doc.id = "abc123"
        mock_doc.set = AsyncMock()
        mock_reminders_coll.document.return_value = mock_doc

        repo = ReminderRepository(mock_client)
        reminder = Reminder(
            user_id=42,
            message="Test",
            trigger_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        )

        doc_id = await repo.create_reminder(reminder)

        assert doc_id == "abc123"
        mock_doc.set.assert_called_once_with(reminder.to_dict())

    async def test_when_getting_pending_reminders_expect_query_built(
        self, mock_firestore_for_reminders
    ) -> None:
        mock_client, mock_reminders_coll = mock_firestore_for_reminders

        mock_doc = MagicMock()
        mock_doc.id = "r1"
        mock_doc.to_dict.return_value = {
            "user_id": 42,
            "message": "Check PRs",
            "trigger_at": datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
            "recurrence": None,
            "status": "pending",
            "created_at": datetime(2026, 5, 1, tzinfo=UTC),
        }

        mock_query = MagicMock()
        mock_query.order_by.return_value = mock_query
        mock_query.get = AsyncMock(return_value=[mock_doc])
        mock_reminders_coll.where.return_value = mock_query

        repo = ReminderRepository(mock_client)
        reminders = await repo.get_pending_reminders(42)

        assert len(reminders) == 1
        assert reminders[0].message == "Check PRs"
        mock_reminders_coll.where.assert_called_once_with("status", "==", "pending")

    async def test_when_cancelling_existing_reminder_expect_true(
        self, mock_firestore_for_reminders
    ) -> None:
        mock_client, mock_reminders_coll = mock_firestore_for_reminders

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_doc_ref.update = AsyncMock()
        mock_reminders_coll.document.return_value = mock_doc_ref

        repo = ReminderRepository(mock_client)
        result = await repo.cancel_reminder(42, "r1")

        assert result is True
        mock_doc_ref.update.assert_called_once_with({"status": "cancelled"})

    async def test_when_cancelling_nonexistent_reminder_expect_false(
        self, mock_firestore_for_reminders
    ) -> None:
        mock_client, mock_reminders_coll = mock_firestore_for_reminders

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_reminders_coll.document.return_value = mock_doc_ref

        repo = ReminderRepository(mock_client)
        result = await repo.cancel_reminder(42, "nonexistent")

        assert result is False

    async def test_when_getting_due_reminders_expect_collection_group_query(
        self, mock_firestore_for_reminders
    ) -> None:
        mock_client, _ = mock_firestore_for_reminders

        mock_doc = MagicMock()
        mock_doc.id = "r2"
        mock_doc.to_dict.return_value = {
            "user_id": 42,
            "message": "Due now",
            "trigger_at": datetime(2026, 1, 1, tzinfo=UTC),
            "recurrence": "daily",
            "status": "pending",
            "created_at": datetime(2025, 12, 1, tzinfo=UTC),
        }

        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.get = AsyncMock(return_value=[mock_doc])
        mock_client.collection_group.return_value = mock_query

        repo = ReminderRepository(mock_client)
        due = await repo.get_due_reminders()

        assert len(due) == 1
        assert due[0].recurrence == Recurrence.DAILY
        mock_client.collection_group.assert_called_once_with("reminders")

    async def test_when_marking_completed_expect_status_updated(
        self, mock_firestore_for_reminders
    ) -> None:
        mock_client, mock_reminders_coll = mock_firestore_for_reminders

        mock_doc_ref = MagicMock()
        mock_doc_ref.update = AsyncMock()
        mock_reminders_coll.document.return_value = mock_doc_ref

        repo = ReminderRepository(mock_client)
        await repo.mark_completed(42, "r1")

        mock_doc_ref.update.assert_called_once_with({"status": "completed"})

    async def test_when_updating_next_trigger_expect_trigger_at_updated(
        self, mock_firestore_for_reminders
    ) -> None:
        mock_client, mock_reminders_coll = mock_firestore_for_reminders

        mock_doc_ref = MagicMock()
        mock_doc_ref.update = AsyncMock()
        mock_reminders_coll.document.return_value = mock_doc_ref

        next_trigger = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

        repo = ReminderRepository(mock_client)
        await repo.update_next_trigger(42, "r1", next_trigger)

        mock_doc_ref.update.assert_called_once_with({"trigger_at": next_trigger})
