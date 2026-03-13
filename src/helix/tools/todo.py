"""Built-in tool: todo — create, list, complete, and delete tasks.

The LLM calls this tool with a ``command`` argument and the appropriate
parameters.  The ``_user_id`` keyword is injected automatically by the
agent loop and is **not** declared in the parameters schema.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from helix.memory.models import Priority, Todo
from helix.memory.todo_repository import TodoRepository
from helix.tools.base import Tool

logger = logging.getLogger(__name__)


class TodoTool(Tool):
    """Create, list, complete, and delete personal tasks."""

    def __init__(self, repository: TodoRepository) -> None:
        self._repo = repository

    @property
    def name(self) -> str:
        return "todo"

    @property
    def description(self) -> str:
        return (
            "Manage personal tasks/todos. "
            "Commands: 'create' (add a new task), "
            "'list' (show pending tasks), "
            "'complete' (mark a task as done), "
            "'delete' (remove a task)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["create", "list", "complete", "delete"],
                    "description": "The action to perform.",
                },
                "title": {
                    "type": "string",
                    "description": "Task title (required for 'create').",
                },
                "description": {
                    "type": "string",
                    "description": "Optional longer description for 'create'.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Priority level (default: medium).",
                },
                "due_date": {
                    "type": "string",
                    "description": "Optional due date in ISO-8601 format (YYYY-MM-DD).",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for categorisation.",
                },
                "todo_id": {
                    "type": "string",
                    "description": "Task ID (required for 'complete' and 'delete').",
                },
            },
            "required": ["command"],
        }

    async def run(self, **kwargs: Any) -> str:
        """Dispatch to the appropriate sub-command."""
        command = kwargs.get("command", "")
        user_id: int = kwargs.get("_user_id", 0)

        if not user_id:
            return "Error: could not determine user identity."

        if command == "create":
            return await self._create(user_id, kwargs)
        if command == "list":
            return await self._list(user_id)
        if command == "complete":
            return await self._complete(user_id, kwargs)
        if command == "delete":
            return await self._delete(user_id, kwargs)

        return f"Error: unknown command '{command}'. Use 'create', 'list', 'complete', or 'delete'."

    async def _create(self, user_id: int, kwargs: dict[str, Any]) -> str:
        title = kwargs.get("title")
        if not title:
            return "Error: 'title' is required for creating a task."

        priority = Priority(kwargs.get("priority", "medium"))

        due_date_str = kwargs.get("due_date")
        due_date_val: date | None = None
        if due_date_str:
            try:
                due_date_val = date.fromisoformat(due_date_str)
            except (ValueError, TypeError):
                return f"Error: invalid date format '{due_date_str}'. Use YYYY-MM-DD."

        todo = Todo(
            user_id=user_id,
            title=title,
            description=kwargs.get("description", ""),
            priority=priority,
            due_date=due_date_val,
            tags=kwargs.get("tags", []),
        )
        doc_id = await self._repo.create_todo(todo)

        parts = [f"Task created (ID: {doc_id}): {title}"]
        if due_date_val:
            parts.append(f"Due: {due_date_val.isoformat()}")
        if priority != Priority.MEDIUM:
            parts.append(f"Priority: {priority.value}")
        return " | ".join(parts)

    async def _list(self, user_id: int) -> str:
        todos = await self._repo.get_todos(user_id)
        if not todos:
            return "You have no pending tasks."

        lines = []
        for t in todos:
            parts = [f"- **{t.id}**: {t.title}"]
            if t.priority != Priority.MEDIUM:
                parts.append(f"[{t.priority.value}]")
            if t.due_date:
                parts.append(f"due {t.due_date.isoformat()}")
            if t.tags:
                parts.append(f"tags: {', '.join(t.tags)}")
            lines.append(" ".join(parts))
        return f"Pending tasks ({len(todos)}):\n" + "\n".join(lines)

    async def _complete(self, user_id: int, kwargs: dict[str, Any]) -> str:
        todo_id = kwargs.get("todo_id")
        if not todo_id:
            return "Error: 'todo_id' is required for completing a task."

        completed = await self._repo.complete_todo(user_id, todo_id)
        if completed:
            return f"Task {todo_id} marked as completed."
        return f"Task {todo_id} not found."

    async def _delete(self, user_id: int, kwargs: dict[str, Any]) -> str:
        todo_id = kwargs.get("todo_id")
        if not todo_id:
            return "Error: 'todo_id' is required for deleting a task."

        deleted = await self._repo.delete_todo(user_id, todo_id)
        if deleted:
            return f"Task {todo_id} has been deleted."
        return f"Task {todo_id} not found."
