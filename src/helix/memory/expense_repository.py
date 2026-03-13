"""Repository layer for expense persistence.

Firestore data model
--------------------
``users/{user_id}/expenses/{expense_id}``
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import AsyncClient

from helix.memory.models import Expense

logger = logging.getLogger(__name__)


class ExpenseRepository:
    """Read/write access to expenses stored in Firestore.

    Args:
        client: An async Firestore client.
    """

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    def _expenses_ref(self, user_id: int) -> Any:
        """Return the ``expenses`` sub-collection for *user_id*."""
        return self._client.collection("users").document(str(user_id)).collection("expenses")

    async def create_expense(self, expense: Expense) -> str:
        """Persist a new expense and return its document ID.

        Args:
            expense: The expense to save.

        Returns:
            The auto-generated Firestore document ID.
        """
        ref = self._expenses_ref(expense.user_id)
        doc_ref = ref.document()
        await doc_ref.set(expense.to_dict())
        logger.info(
            "Expense created",
            extra={"user_id": expense.user_id, "doc_id": doc_ref.id, "amount": expense.amount},
        )
        return doc_ref.id

    async def get_expenses(
        self,
        user_id: int,
        *,
        month: int | None = None,
        year: int | None = None,
    ) -> list[Expense]:
        """Return expenses for a user, optionally filtered to a month.

        Without *month*/*year* the current month is used.

        Args:
            user_id: Telegram user ID.
            month: Month number (1-12).
            year: Year (e.g. 2025).

        Returns:
            A list of ``Expense`` instances.
        """
        now = datetime.now(UTC)
        month = month or now.month
        year = year or now.year

        start_date = f"{year:04d}-{month:02d}-01"
        end_date = f"{year + 1:04d}-01-01" if month == 12 else f"{year:04d}-{month + 1:02d}-01"

        ref = self._expenses_ref(user_id)
        query = (
            ref.where("expense_date", ">=", start_date)
            .where("expense_date", "<", end_date)
            .order_by("expense_date")
        )
        docs = await query.get()
        return [Expense.from_dict(doc.to_dict(), doc.id) for doc in docs]

    async def delete_expense(self, user_id: int, expense_id: str) -> bool:
        """Delete an expense.

        Args:
            user_id: Telegram user ID.
            expense_id: Firestore document ID.

        Returns:
            ``True`` if the expense existed and was deleted, ``False`` otherwise.
        """
        doc_ref = self._expenses_ref(user_id).document(expense_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False
        await doc_ref.delete()
        logger.info(
            "Expense deleted",
            extra={"user_id": user_id, "expense_id": expense_id},
        )
        return True
