"""Shared test fixtures for the Helix test suite."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from helix.config.settings import (
    AgentConfig,
    LLMConfig,
    LoggingConfig,
    MemoryConfig,
    Settings,
    SkillConfig,
)
from helix.memory.models import Message
from helix.memory.repositories import ChatHistoryRepository
from helix.tools.get_current_time import GetCurrentTimeTool
from helix.tools.registry import ToolRegistry


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Minimal settings for unit tests (no real tokens)."""
    prompt = tmp_path / "prompt.md"
    prompt.write_text(
        "You are a test assistant.\n\n"
        "Current UTC time: {current_time}\n\n"
        "Tools:\n{tools_description}"
    )
    return Settings(
        telegram_bot_token="123456789:AAFake-Token_ForUnitTestsOnly",
        telegram_allowed_user_ids=[12345],
        groq_api_key="gsk_test_fake_key_for_unit_tests",
        openrouter_api_key="sk-or-v1-test_fake_key",
        llm=LLMConfig(),
        agent=AgentConfig(
            max_iterations=3,
            history_limit=10,
            system_prompt_path=str(prompt),
        ),
        memory=MemoryConfig(project_id="test-project"),
        logging=LoggingConfig(level="DEBUG"),
        skills=[SkillConfig(name="get_current_time", type="builtin")],
    )


@pytest.fixture
def mock_firestore_client():
    """Returns a mock AsyncClient that models the sub-collection chain.

    Firestore path: ``users/{user_id}/messages/{message_id}``
    """
    mock_client = MagicMock()

    # users collection → user document → messages sub-collection
    mock_users_coll = MagicMock()
    mock_user_doc = MagicMock()
    mock_messages_coll = MagicMock()

    mock_client.collection.return_value = mock_users_coll
    mock_users_coll.document.return_value = mock_user_doc
    mock_user_doc.collection.return_value = mock_messages_coll

    # Write path: messages_coll.document() → msg_doc with async set()
    mock_msg_doc = MagicMock()
    mock_msg_doc.set = AsyncMock()
    mock_messages_coll.document.return_value = mock_msg_doc

    # Read path: messages_coll.order_by().limit() → query with async get()
    mock_query = MagicMock()
    mock_query.get = AsyncMock(return_value=[])
    mock_messages_coll.order_by.return_value.limit.return_value = mock_query

    return mock_client


@pytest.fixture
def repository(mock_firestore_client) -> ChatHistoryRepository:
    """A mock ChatHistoryRepository for most tests.
    test_repositories.py which can test real repository logic.
    """
    repo = AsyncMock(spec=ChatHistoryRepository)
    repo.get_recent_history.return_value = []

    async def mock_save_message(**kwargs):
        return Message(
            id="mock-id",
            user_id=kwargs.get("user_id", 0),
            role=kwargs.get("role", ""),
            content=kwargs.get("content", ""),
        )

    repo.save_message.side_effect = mock_save_message

    # Also store an internal history list if tests want to check it
    repo.history = []

    async def mock_save_and_store(**kwargs):
        msg = await mock_save_message(**kwargs)
        repo.history.append(msg)
        repo.get_recent_history.return_value = repo.history
        return msg

    repo.save_message.side_effect = mock_save_and_store
    return repo


@pytest.fixture
def tool_registry() -> ToolRegistry:
    """A ``ToolRegistry`` pre-loaded with the built-in tools."""
    registry = ToolRegistry()
    registry.register(GetCurrentTimeTool())
    return registry
