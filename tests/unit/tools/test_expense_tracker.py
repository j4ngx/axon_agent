"""Tests for the ``ExpenseTrackerTool``."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest
from freezegun import freeze_time

from helix.memory.expense_repository import ExpenseRepository
from helix.memory.models import Expense, ExpenseCategory
from helix.tools.expense_tracker import ExpenseTrackerTool


@pytest.fixture
def mock_expense_repo() -> AsyncMock:
    return AsyncMock(spec=ExpenseRepository)


@pytest.fixture
def expense_tool(mock_expense_repo: AsyncMock) -> ExpenseTrackerTool:
    return ExpenseTrackerTool(repository=mock_expense_repo)


class TestExpenseTrackerTool:
    """Unit tests for ``ExpenseTrackerTool``."""

    def test_when_checking_name_expect_expense_tracker(
        self, expense_tool: ExpenseTrackerTool
    ) -> None:
        assert expense_tool.name == "expense_tracker"

    def test_when_checking_schema_expect_command_required(
        self, expense_tool: ExpenseTrackerTool
    ) -> None:
        schema = expense_tool.parameters_schema
        assert "command" in schema["properties"]
        assert schema["required"] == ["command"]

    async def test_when_no_user_id_expect_error(self, expense_tool: ExpenseTrackerTool) -> None:
        result = await expense_tool.run(command="list")
        assert "Error" in result

    @freeze_time("2026-03-15 10:00:00", tz_offset=0)
    async def test_when_adding_expense_expect_success(
        self,
        expense_tool: ExpenseTrackerTool,
        mock_expense_repo: AsyncMock,
    ) -> None:
        mock_expense_repo.create_expense.return_value = "exp123"

        result = await expense_tool.run(
            command="add",
            amount=25.50,
            category="food",
            description="Lunch",
            _user_id=42,
        )

        assert "exp123" in result
        assert "25.50" in result
        assert "food" in result
        mock_expense_repo.create_expense.assert_called_once()

    async def test_when_adding_without_amount_expect_error(
        self, expense_tool: ExpenseTrackerTool
    ) -> None:
        result = await expense_tool.run(
            command="add",
            category="food",
            _user_id=42,
        )
        assert "Error" in result
        assert "amount" in result.lower()

    async def test_when_adding_without_category_expect_error(
        self, expense_tool: ExpenseTrackerTool
    ) -> None:
        result = await expense_tool.run(
            command="add",
            amount=10.0,
            _user_id=42,
        )
        assert "Error" in result
        assert "category" in result.lower()

    async def test_when_adding_negative_amount_expect_error(
        self, expense_tool: ExpenseTrackerTool
    ) -> None:
        result = await expense_tool.run(
            command="add",
            amount=-5.0,
            category="food",
            _user_id=42,
        )
        assert "Error" in result
        assert "positive" in result.lower()

    async def test_when_adding_invalid_category_expect_error(
        self, expense_tool: ExpenseTrackerTool
    ) -> None:
        result = await expense_tool.run(
            command="add",
            amount=10.0,
            category="magic",
            _user_id=42,
        )
        assert "Error" in result
        assert "invalid category" in result.lower()

    async def test_when_adding_with_custom_date_expect_correct_date(
        self,
        expense_tool: ExpenseTrackerTool,
        mock_expense_repo: AsyncMock,
    ) -> None:
        mock_expense_repo.create_expense.return_value = "d1"

        result = await expense_tool.run(
            command="add",
            amount=50.0,
            category="transport",
            expense_date="2026-03-10",
            _user_id=42,
        )

        assert "2026-03-10" in result
        call_args = mock_expense_repo.create_expense.call_args[0][0]
        assert call_args.expense_date == date(2026, 3, 10)

    async def test_when_adding_with_invalid_date_expect_error(
        self, expense_tool: ExpenseTrackerTool
    ) -> None:
        result = await expense_tool.run(
            command="add",
            amount=10.0,
            category="food",
            expense_date="nope",
            _user_id=42,
        )
        assert "Error" in result

    async def test_when_listing_expenses_expect_formatted_output(
        self,
        expense_tool: ExpenseTrackerTool,
        mock_expense_repo: AsyncMock,
    ) -> None:
        mock_expense_repo.get_expenses.return_value = [
            Expense(
                id="e1",
                user_id=42,
                amount=25.0,
                currency="EUR",
                category=ExpenseCategory.FOOD,
                description="Lunch",
                expense_date=date(2026, 3, 15),
            ),
            Expense(
                id="e2",
                user_id=42,
                amount=10.0,
                currency="EUR",
                category=ExpenseCategory.TRANSPORT,
                expense_date=date(2026, 3, 16),
            ),
        ]

        result = await expense_tool.run(command="list", _user_id=42)

        assert "35.00" in result  # Total
        assert "Lunch" in result
        assert "food" in result
        assert "transport" in result

    async def test_when_listing_empty_expect_no_expenses_message(
        self,
        expense_tool: ExpenseTrackerTool,
        mock_expense_repo: AsyncMock,
    ) -> None:
        mock_expense_repo.get_expenses.return_value = []

        result = await expense_tool.run(command="list", _user_id=42)

        assert "no expenses" in result.lower()

    async def test_when_summary_expect_category_breakdown(
        self,
        expense_tool: ExpenseTrackerTool,
        mock_expense_repo: AsyncMock,
    ) -> None:
        mock_expense_repo.get_expenses.return_value = [
            Expense(
                id="e1",
                user_id=42,
                amount=50.0,
                category=ExpenseCategory.FOOD,
                expense_date=date(2026, 3, 15),
            ),
            Expense(
                id="e2",
                user_id=42,
                amount=30.0,
                category=ExpenseCategory.FOOD,
                expense_date=date(2026, 3, 16),
            ),
            Expense(
                id="e3",
                user_id=42,
                amount=20.0,
                category=ExpenseCategory.TRANSPORT,
                expense_date=date(2026, 3, 17),
            ),
        ]

        result = await expense_tool.run(command="summary", _user_id=42)

        assert "100.00" in result  # Total
        assert "food" in result
        assert "80.00" in result  # Food total
        assert "transport" in result
        assert "20.00" in result  # Transport total

    async def test_when_deleting_existing_expect_success(
        self,
        expense_tool: ExpenseTrackerTool,
        mock_expense_repo: AsyncMock,
    ) -> None:
        mock_expense_repo.delete_expense.return_value = True

        result = await expense_tool.run(
            command="delete",
            expense_id="e1",
            _user_id=42,
        )

        assert "deleted" in result.lower()
        mock_expense_repo.delete_expense.assert_called_once_with(42, "e1")

    async def test_when_deleting_nonexistent_expect_not_found(
        self,
        expense_tool: ExpenseTrackerTool,
        mock_expense_repo: AsyncMock,
    ) -> None:
        mock_expense_repo.delete_expense.return_value = False

        result = await expense_tool.run(
            command="delete",
            expense_id="nope",
            _user_id=42,
        )

        assert "not found" in result.lower()

    async def test_when_deleting_without_id_expect_error(
        self, expense_tool: ExpenseTrackerTool
    ) -> None:
        result = await expense_tool.run(command="delete", _user_id=42)
        assert "Error" in result
        assert "expense_id" in result.lower()

    async def test_when_unknown_command_expect_error(
        self, expense_tool: ExpenseTrackerTool
    ) -> None:
        result = await expense_tool.run(command="refund", _user_id=42)
        assert "Error" in result
        assert "unknown command" in result.lower()
