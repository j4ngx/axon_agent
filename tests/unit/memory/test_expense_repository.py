"""Tests for the ``ExpenseRepository``."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from helix.memory.expense_repository import ExpenseRepository
from helix.memory.models import Expense, ExpenseCategory


@pytest.fixture
def mock_firestore_for_expenses():
    """Mock Firestore client modelling ``users/{uid}/expenses/{eid}``."""
    mock_client = MagicMock()
    mock_users_coll = MagicMock()
    mock_user_doc = MagicMock()
    mock_expenses_coll = MagicMock()

    mock_client.collection.return_value = mock_users_coll
    mock_users_coll.document.return_value = mock_user_doc
    mock_user_doc.collection.return_value = mock_expenses_coll

    return mock_client, mock_expenses_coll


class TestExpenseRepository:
    """Unit tests for ``ExpenseRepository``."""

    async def test_when_creating_expense_expect_doc_set_called(
        self, mock_firestore_for_expenses
    ) -> None:
        mock_client, mock_expenses_coll = mock_firestore_for_expenses
        mock_doc = MagicMock()
        mock_doc.id = "exp123"
        mock_doc.set = AsyncMock()
        mock_expenses_coll.document.return_value = mock_doc

        repo = ExpenseRepository(mock_client)
        expense = Expense(
            user_id=42,
            amount=15.50,
            category=ExpenseCategory.FOOD,
            description="Lunch",
        )

        doc_id = await repo.create_expense(expense)

        assert doc_id == "exp123"
        mock_doc.set.assert_called_once_with(expense.to_dict())

    async def test_when_getting_expenses_expect_date_range_query(
        self, mock_firestore_for_expenses
    ) -> None:
        mock_client, mock_expenses_coll = mock_firestore_for_expenses

        mock_doc = MagicMock()
        mock_doc.id = "e1"
        mock_doc.to_dict.return_value = {
            "user_id": 42,
            "amount": 25.0,
            "currency": "EUR",
            "category": "food",
            "description": "Groceries",
            "expense_date": "2026-03-15",
            "tags": [],
            "created_at": datetime(2026, 3, 15, tzinfo=UTC),
        }

        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_query2.order_by.return_value = mock_query2
        mock_query2.get = AsyncMock(return_value=[mock_doc])
        mock_query1.where.return_value = mock_query2
        mock_expenses_coll.where.return_value = mock_query1

        repo = ExpenseRepository(mock_client)
        expenses = await repo.get_expenses(42, month=3, year=2026)

        assert len(expenses) == 1
        assert expenses[0].amount == 25.0
        mock_expenses_coll.where.assert_called_once_with("expense_date", ">=", "2026-03-01")

    async def test_when_deleting_existing_expense_expect_true(
        self, mock_firestore_for_expenses
    ) -> None:
        mock_client, mock_expenses_coll = mock_firestore_for_expenses

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_doc_ref.delete = AsyncMock()
        mock_expenses_coll.document.return_value = mock_doc_ref

        repo = ExpenseRepository(mock_client)
        result = await repo.delete_expense(42, "e1")

        assert result is True
        mock_doc_ref.delete.assert_called_once()

    async def test_when_deleting_nonexistent_expense_expect_false(
        self, mock_firestore_for_expenses
    ) -> None:
        mock_client, mock_expenses_coll = mock_firestore_for_expenses

        mock_doc_ref = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_expenses_coll.document.return_value = mock_doc_ref

        repo = ExpenseRepository(mock_client)
        result = await repo.delete_expense(42, "nonexistent")

        assert result is False

    async def test_when_getting_december_expenses_expect_correct_end_date(
        self, mock_firestore_for_expenses
    ) -> None:
        """Edge case: December should roll over to January of next year."""
        mock_client, mock_expenses_coll = mock_firestore_for_expenses

        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_query2.order_by.return_value = mock_query2
        mock_query2.get = AsyncMock(return_value=[])
        mock_query1.where.return_value = mock_query2
        mock_expenses_coll.where.return_value = mock_query1

        repo = ExpenseRepository(mock_client)
        await repo.get_expenses(42, month=12, year=2026)

        mock_expenses_coll.where.assert_called_once_with("expense_date", ">=", "2026-12-01")
        mock_query1.where.assert_called_once_with("expense_date", "<", "2027-01-01")
