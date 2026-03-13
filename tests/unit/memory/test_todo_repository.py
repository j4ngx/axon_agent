"""Tests for the ``TodoRepository``."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from helix.memory.models import Priority, Todo
from helix.memory.todo_repository import TodoRepository


@pytest.fixture
def mock_firestore_for_todos():
    """Mock Firestore client modelling ``users/{uid}/todos/{tid}``."""
    mock_client = MagicMock()
    mock_users_coll = MagicMock()
    mock_user_doc = MagicMock()
    mock_todos_coll = MagicMock()

    mock_client.collection.return_value = mock_users_coll
    mock_users_coll.document.return_value = mock_user_doc
    mock_user_doc.collection.return_value = mock_todos_coll

    return mock_client, mock_todos_coll


class TestTodoRepository:
    """Unit tests for ``TodoRepository``."""

    async def test_when_creating_todo_expect_doc_set_called(self, mock_firestore_for_todos) -> None:
        mock_client, mock_todos_coll = mock_firestore_for_todos
        mock_doc = MagicMock()
        mock_doc.id = "todo123"
        mock_doc.set = AsyncMock()
        mock_todos_coll.document.return_value = mock_doc

        repo = TodoRepository(mock_client)
        todo = Todo(user_id=42, title="Buy milk", priority=Priority.HIGH)

        doc_id = await repo.create_todo(todo)

        assert doc_id == "todo123"
        mock_doc.set.assert_called_once_with(todo.to_dict())

    async def test_when_getting_todos_expect_query_built(self, mock_firestore_for_todos) -> None:
        mock_client, mock_todos_coll = mock_firestore_for_todos

        mock_doc = MagicMock()
        mock_doc.id = "t1"
        mock_doc.to_dict.return_value = {
            "user_id": 42,
            "title": "Write tests",
            "description": "",
            "priority": "medium",
            "due_date": None,
            "tags": [],
            "status": "pending",
            "created_at": datetime(2026, 5, 1, tzinfo=UTC),
            "completed_at": None,
        }

        mock_query = MagicMock()
        mock_query.order_by.return_value = mock_query
        mock_query.get = AsyncMock(return_value=[mock_doc])
        mock_todos_coll.where.return_value = mock_query

        repo = TodoRepository(mock_client)
        todos = await repo.get_todos(42)

        assert len(todos) == 1
        assert todos[0].title == "Write tests"
        mock_todos_coll.where.assert_called_once_with("status", "==", "pending")

    async def test_when_completing_existing_todo_expect_true(
        self, mock_firestore_for_todos
    ) -> None:
        mock_client, mock_todos_coll = mock_firestore_for_todos

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_doc_ref.update = AsyncMock()
        mock_todos_coll.document.return_value = mock_doc_ref

        repo = TodoRepository(mock_client)
        result = await repo.complete_todo(42, "t1")

        assert result is True
        mock_doc_ref.update.assert_called_once()
        call_data = mock_doc_ref.update.call_args[0][0]
        assert call_data["status"] == "completed"
        assert "completed_at" in call_data

    async def test_when_completing_nonexistent_todo_expect_false(
        self, mock_firestore_for_todos
    ) -> None:
        mock_client, mock_todos_coll = mock_firestore_for_todos

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_todos_coll.document.return_value = mock_doc_ref

        repo = TodoRepository(mock_client)
        result = await repo.complete_todo(42, "nonexistent")

        assert result is False

    async def test_when_deleting_existing_todo_expect_true(self, mock_firestore_for_todos) -> None:
        mock_client, mock_todos_coll = mock_firestore_for_todos

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_doc_ref.delete = AsyncMock()
        mock_todos_coll.document.return_value = mock_doc_ref

        repo = TodoRepository(mock_client)
        result = await repo.delete_todo(42, "t1")

        assert result is True
        mock_doc_ref.delete.assert_called_once()

    async def test_when_deleting_nonexistent_todo_expect_false(
        self, mock_firestore_for_todos
    ) -> None:
        mock_client, mock_todos_coll = mock_firestore_for_todos

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_todos_coll.document.return_value = mock_doc_ref

        repo = TodoRepository(mock_client)
        result = await repo.delete_todo(42, "nonexistent")

        assert result is False
