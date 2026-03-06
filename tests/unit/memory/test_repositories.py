"""Tests for the ``ChatHistoryRepository``."""

from __future__ import annotations

from datetime import UTC, datetime

from axon.memory.repositories import ChatHistoryRepository


class TestChatHistoryRepository:
    """Unit tests for ``ChatHistoryRepository``."""

    async def test_when_saving_message_expect_id_populated(
        self, repository: ChatHistoryRepository
    ) -> None:
        msg = await repository.save_message(user_id=1, role="user", content="hello")
        assert msg.id is not None
        assert msg.user_id == 1
        assert msg.role == "user"
        assert msg.content == "hello"

    async def test_when_saving_message_expect_timestamp_set(
        self, repository: ChatHistoryRepository
    ) -> None:
        msg = await repository.save_message(user_id=1, role="user", content="hi")
        assert msg.timestamp is not None
        # Note: SQLite does not natively preserve timezone info.
        assert msg.timestamp.year >= 2026

    async def test_when_saving_with_explicit_timestamp_expect_it_used(
        self, repository: ChatHistoryRepository
    ) -> None:
        ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        msg = await repository.save_message(
            user_id=1, role="user", content="explicit", timestamp=ts
        )
        # SQLite strips tzinfo — compare naive values.
        assert msg.timestamp.replace(tzinfo=None) == ts.replace(tzinfo=None)

    async def test_when_fetching_history_expect_chronological_order(
        self, repository: ChatHistoryRepository
    ) -> None:
        for i in range(5):
            await repository.save_message(
                user_id=42,
                role="user" if i % 2 == 0 else "assistant",
                content=f"msg-{i}",
            )
        history = await repository.get_recent_history(user_id=42, limit=10)
        assert len(history) == 5
        # Oldest first
        assert history[0].content == "msg-0"
        assert history[-1].content == "msg-4"

    async def test_when_fetching_with_limit_expect_only_latest(
        self, repository: ChatHistoryRepository
    ) -> None:
        for i in range(10):
            await repository.save_message(user_id=7, role="user", content=f"msg-{i}")
        history = await repository.get_recent_history(user_id=7, limit=3)
        assert len(history) == 3
        # The last 3 messages, oldest first
        assert history[0].content == "msg-7"
        assert history[2].content == "msg-9"

    async def test_when_fetching_different_user_expect_isolation(
        self, repository: ChatHistoryRepository
    ) -> None:
        await repository.save_message(user_id=1, role="user", content="user1")
        await repository.save_message(user_id=2, role="user", content="user2")

        h1 = await repository.get_recent_history(user_id=1, limit=10)
        h2 = await repository.get_recent_history(user_id=2, limit=10)

        assert len(h1) == 1
        assert h1[0].content == "user1"
        assert len(h2) == 1
        assert h2[0].content == "user2"

    async def test_when_no_messages_expect_empty_list(
        self, repository: ChatHistoryRepository
    ) -> None:
        history = await repository.get_recent_history(user_id=999, limit=10)
        assert history == []
