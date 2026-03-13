"""Built-in tool: expense_tracker — log, list, and summarise expenses.

The LLM calls this tool with a ``command`` argument and the appropriate
parameters.  The ``_user_id`` keyword is injected automatically by the
agent loop and is **not** declared in the parameters schema.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from helix.memory.expense_repository import ExpenseRepository
from helix.memory.models import Expense, ExpenseCategory
from helix.tools.base import Tool

logger = logging.getLogger(__name__)


class ExpenseTrackerTool(Tool):
    """Log, list, and summarise personal expenses."""

    def __init__(self, repository: ExpenseRepository) -> None:
        self._repo = repository

    @property
    def name(self) -> str:
        return "expense_tracker"

    @property
    def description(self) -> str:
        return (
            "Track personal expenses and spending. "
            "Commands: 'add' (log a new expense), "
            "'list' (show expenses for a month), "
            "'summary' (category breakdown for a month), "
            "'delete' (remove an expense)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["add", "list", "summary", "delete"],
                    "description": "The action to perform.",
                },
                "amount": {
                    "type": "number",
                    "description": "Expense amount (required for 'add').",
                },
                "category": {
                    "type": "string",
                    "enum": [c.value for c in ExpenseCategory],
                    "description": "Expense category (required for 'add').",
                },
                "description": {
                    "type": "string",
                    "description": "Short note about the expense (optional).",
                },
                "currency": {
                    "type": "string",
                    "description": "ISO 4217 currency code (default: EUR).",
                },
                "expense_date": {
                    "type": "string",
                    "description": "Date of expense YYYY-MM-DD (default: today).",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags.",
                },
                "month": {
                    "type": "integer",
                    "description": "Month number 1-12 (for 'list'/'summary').",
                },
                "year": {
                    "type": "integer",
                    "description": "Year (for 'list'/'summary').",
                },
                "expense_id": {
                    "type": "string",
                    "description": "Expense ID (required for 'delete').",
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

        if command == "add":
            return await self._add(user_id, kwargs)
        if command == "list":
            return await self._list(user_id, kwargs)
        if command == "summary":
            return await self._summary(user_id, kwargs)
        if command == "delete":
            return await self._delete(user_id, kwargs)

        return f"Error: unknown command '{command}'. Use 'add', 'list', 'summary', or 'delete'."

    async def _add(self, user_id: int, kwargs: dict[str, Any]) -> str:
        amount = kwargs.get("amount")
        category_str = kwargs.get("category")

        if amount is None:
            return "Error: 'amount' is required for adding an expense."
        if not category_str:
            return "Error: 'category' is required for adding an expense."

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return f"Error: invalid amount '{amount}'."

        if amount <= 0:
            return "Error: amount must be positive."

        try:
            category = ExpenseCategory(category_str)
        except ValueError:
            valid = ", ".join(c.value for c in ExpenseCategory)
            return f"Error: invalid category '{category_str}'. Valid: {valid}"

        expense_date_str = kwargs.get("expense_date")
        expense_date_val = datetime.now(UTC).date()
        if expense_date_str:
            try:
                expense_date_val = date.fromisoformat(expense_date_str)
            except (ValueError, TypeError):
                return f"Error: invalid date format '{expense_date_str}'. Use YYYY-MM-DD."

        expense = Expense(
            user_id=user_id,
            amount=amount,
            currency=kwargs.get("currency", "EUR"),
            category=category,
            description=kwargs.get("description", ""),
            expense_date=expense_date_val,
            tags=kwargs.get("tags", []),
        )
        doc_id = await self._repo.create_expense(expense)
        return (
            f"Expense logged (ID: {doc_id}): "
            f"{expense.currency} {amount:.2f} [{category.value}] "
            f"on {expense_date_val.isoformat()}"
        )

    async def _list(self, user_id: int, kwargs: dict[str, Any]) -> str:
        month = kwargs.get("month")
        year = kwargs.get("year")
        expenses = await self._repo.get_expenses(user_id, month=month, year=year)
        if not expenses:
            return "No expenses found for the requested period."

        total = sum(e.amount for e in expenses)
        currency = expenses[0].currency

        lines = []
        for e in expenses:
            desc = f" — {e.description}" if e.description else ""
            lines.append(
                f"- **{e.id}**: {e.currency} {e.amount:.2f} [{e.category.value}] "
                f"{e.expense_date.isoformat()}{desc}"
            )
        header = f"Expenses ({len(expenses)}) — Total: {currency} {total:.2f}\n"
        return header + "\n".join(lines)

    async def _summary(self, user_id: int, kwargs: dict[str, Any]) -> str:
        month = kwargs.get("month")
        year = kwargs.get("year")
        expenses = await self._repo.get_expenses(user_id, month=month, year=year)
        if not expenses:
            return "No expenses found for the requested period."

        by_category: dict[str, float] = {}
        total = 0.0
        currency = expenses[0].currency
        for e in expenses:
            by_category[e.category.value] = by_category.get(e.category.value, 0) + e.amount
            total += e.amount

        # Sort by amount descending
        sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
        lines = [f"- **{cat}**: {currency} {amt:.2f}" for cat, amt in sorted_cats]
        return f"Expense summary — Total: {currency} {total:.2f}\n" + "\n".join(lines)

    async def _delete(self, user_id: int, kwargs: dict[str, Any]) -> str:
        expense_id = kwargs.get("expense_id")
        if not expense_id:
            return "Error: 'expense_id' is required for deleting an expense."

        deleted = await self._repo.delete_expense(user_id, expense_id)
        if deleted:
            return f"Expense {expense_id} has been deleted."
        return f"Expense {expense_id} not found."
