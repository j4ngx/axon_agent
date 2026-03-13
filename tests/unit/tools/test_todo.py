"""Tests for the ``TodoTool``."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from helix.memory.models import Priority, Todo
from helix.memory.todo_repository import TodoRepository
from helix.tools.todo import TodoTool


@pytest.fixture
def mock_todo_repo() -> AsyncMock:
    return AsyncMock(spec=TodoRepository)


@pytest.fixture
def todo_tool(mock_todo_repo: AsyncMock) -> TodoTool:
    return TodoTool(repository=mock_todo_repo)


class TestTodoTool:
    """Unit tests for ``TodoTool``."""

    def test_when_checking_name_expect_todo(self, todo_tool: TodoTool) -> None:
        assert todo_tool.name == "todo"

    def test_when_checking_schema_expect_command_required(self, todo_tool: TodoTool) -> None:
        schema = todo_tool.parameters_schema
        assert "command" in schema["properties"]
        assert schema["required"] == ["command"]

    async def test_when_no_user_id_expect_error(self, todo_tool: TodoTool) -> None:
        result = await todo_tool.run(command="list")
        assert "Error" in result

    async def test_when_creating_todo_expect_success(
        self,
        todo_tool: TodoTool,
        mock_todo_repo: AsyncMock,
    ) -> None:
        mock_todo_repo.create_todo.return_value = "todo123"

        result = await todo_tool.run(
            command="create",
            title="Buy groceries",
            _user_id=42,
        )

        assert "todo123" in result
        assert "Task created" in result
        mock_todo_repo.create_todo.assert_called_once()

    async def test_when_creating_with_priority_expect_priority_in_response(
        self,
        todo_tool: TodoTool,
        mock_todo_repo: AsyncMock,
    ) -> None:
        mock_todo_repo.create_todo.return_value = "p1"

        result = await todo_tool.run(
            command="create",
            title="Urgent task",
            priority="urgent",
            _user_id=42,
        )

        assert "urgent" in result.lower()
        call_args = mock_todo_repo.create_todo.call_args[0][0]
        assert call_args.priority == Priority.URGENT

    async def test_when_creating_with_due_date_expect_date_in_response(
        self,
        todo_tool: TodoTool,
        mock_todo_repo: AsyncMock,
    ) -> None:
        mock_todo_repo.create_todo.return_value = "d1"

        result = await todo_tool.run(
            command="create",
            title="Deadline task",
            due_date="2026-06-01",
            _user_id=42,
        )

        assert "2026-06-01" in result
        call_args = mock_todo_repo.create_todo.call_args[0][0]
        assert call_args.due_date == date(2026, 6, 1)

    async def test_when_creating_without_title_expect_error(self, todo_tool: TodoTool) -> None:
        result = await todo_tool.run(command="create", _user_id=42)
        assert "Error" in result
        assert "title" in result.lower()

    async def test_when_creating_with_invalid_date_expect_error(self, todo_tool: TodoTool) -> None:
        result = await todo_tool.run(
            command="create",
            title="Test",
            due_date="not-a-date",
            _user_id=42,
        )
        assert "Error" in result
        assert "YYYY-MM-DD" in result

    async def test_when_listing_todos_expect_formatted_output(
        self,
        todo_tool: TodoTool,
        mock_todo_repo: AsyncMock,
    ) -> None:
        mock_todo_repo.get_todos.return_value = [
            Todo(
                id="t1",
                user_id=42,
                title="Buy milk",
                priority=Priority.HIGH,
                due_date=date(2026, 6, 1),
            ),
            Todo(
                id="t2",
                user_id=42,
                title="Read book",
                tags=["personal"],
            ),
        ]

        result = await todo_tool.run(command="list", _user_id=42)

        assert "2" in result
        assert "Buy milk" in result
        assert "Read book" in result
        assert "[high]" in result
        assert "personal" in result

    async def test_when_listing_empty_expect_no_tasks_message(
        self,
        todo_tool: TodoTool,
        mock_todo_repo: AsyncMock,
    ) -> None:
        mock_todo_repo.get_todos.return_value = []

        result = await todo_tool.run(command="list", _user_id=42)

        assert "no pending" in result.lower()

    async def test_when_completing_existing_expect_success(
        self,
        todo_tool: TodoTool,
        mock_todo_repo: AsyncMock,
    ) -> None:
        mock_todo_repo.complete_todo.return_value = True

        result = await todo_tool.run(
            command="complete",
            todo_id="t1",
            _user_id=42,
        )

        assert "completed" in result.lower()
        mock_todo_repo.complete_todo.assert_called_once_with(42, "t1")

    async def test_when_completing_nonexistent_expect_not_found(
        self,
        todo_tool: TodoTool,
        mock_todo_repo: AsyncMock,
    ) -> None:
        mock_todo_repo.complete_todo.return_value = False

        result = await todo_tool.run(
            command="complete",
            todo_id="nope",
            _user_id=42,
        )

        assert "not found" in result.lower()

    async def test_when_completing_without_id_expect_error(self, todo_tool: TodoTool) -> None:
        result = await todo_tool.run(command="complete", _user_id=42)
        assert "Error" in result
        assert "todo_id" in result.lower()

    async def test_when_deleting_existing_expect_success(
        self,
        todo_tool: TodoTool,
        mock_todo_repo: AsyncMock,
    ) -> None:
        mock_todo_repo.delete_todo.return_value = True

        result = await todo_tool.run(
            command="delete",
            todo_id="t1",
            _user_id=42,
        )

        assert "deleted" in result.lower()
        mock_todo_repo.delete_todo.assert_called_once_with(42, "t1")

    async def test_when_deleting_nonexistent_expect_not_found(
        self,
        todo_tool: TodoTool,
        mock_todo_repo: AsyncMock,
    ) -> None:
        mock_todo_repo.delete_todo.return_value = False

        result = await todo_tool.run(
            command="delete",
            todo_id="nope",
            _user_id=42,
        )

        assert "not found" in result.lower()

    async def test_when_unknown_command_expect_error(self, todo_tool: TodoTool) -> None:
        result = await todo_tool.run(command="fly", _user_id=42)
        assert "Error" in result
        assert "unknown command" in result.lower()
