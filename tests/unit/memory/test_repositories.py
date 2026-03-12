"""Tests for the ``ChatHistoryRepository``."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from helix.memory.repositories import ChatHistoryRepository


class TestChatHistoryRepository:
    """Unit tests for ``ChatHistoryRepository``."""

    async def test_when_saving_message_expect_doc_set(
        self, mock_firestore_client: MagicMock
    ) -> None:
        repository = ChatHistoryRepository(mock_firestore_client)
        # Navigate: users → {uid} → messages → {doc}
        mock_user_doc = mock_firestore_client.collection.return_value.document.return_value
        mock_msg_doc = mock_user_doc.collection.return_value.document.return_value
        mock_msg_doc.id = "test-doc-123"

        msg = await repository.save_message(user_id=1, role="user", content="hello")

        assert msg.id == "test-doc-123"
        assert msg.user_id == 1
        assert msg.role == "user"
        assert msg.content == "hello"
        mock_msg_doc.set.assert_called_once()
        saved_dict = mock_msg_doc.set.call_args[0][0]
        assert saved_dict["user_id"] == 1
        assert saved_dict["role"] == "user"

    async def test_when_saving_with_explicit_timestamp_expect_it_used(
        self, mock_firestore_client: MagicMock
    ) -> None:
        repository = ChatHistoryRepository(mock_firestore_client)
        ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        msg = await repository.save_message(
            user_id=1, role="user", content="explicit", timestamp=ts
        )
        assert msg.timestamp == ts

    async def test_when_fetching_history_expect_chronological_order(
        self, mock_firestore_client: MagicMock
    ) -> None:
        repository = ChatHistoryRepository(mock_firestore_client)
        # Navigate: users → {uid} → messages
        mock_user_doc = mock_firestore_client.collection.return_value.document.return_value
        mock_messages_coll = mock_user_doc.collection.return_value
        mock_query = mock_messages_coll.order_by.return_value.limit.return_value

        # Mock returned docs (descending order from Firestore)
        doc1 = MagicMock()
        doc1.id = "msg2"
        doc1.to_dict.return_value = {
            "content": "msg-2",
            "user_id": 42,
            "role": "assistant",
            "timestamp": datetime.now(UTC),
        }

        doc2 = MagicMock()
        doc2.id = "msg1"
        doc2.to_dict.return_value = {
            "content": "msg-1",
            "user_id": 42,
            "role": "user",
            "timestamp": datetime.now(UTC),
        }

        mock_query.get = AsyncMock(return_value=[doc1, doc2])

        history = await repository.get_recent_history(user_id=42, limit=10)
        assert len(history) == 2
        # Returned in reversed order (oldest first logic)
        assert history[0].content == "msg-1"
        assert history[1].content == "msg-2"
