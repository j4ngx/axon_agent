"""Shared test fixtures for the Axon test suite."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from axon.config.settings import (
    AgentConfig,
    LLMConfig,
    LoggingConfig,
    MemoryConfig,
    Settings,
    SkillConfig,
)
from axon.memory.db import init_db
from axon.memory.repositories import ChatHistoryRepository
from axon.tools.get_current_time import GetCurrentTimeTool
from axon.tools.registry import ToolRegistry


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
        memory=MemoryConfig(db_path=":memory:"),
        logging=LoggingConfig(level="DEBUG"),
        skills=[SkillConfig(name="get_current_time", type="builtin")],
    )


@pytest.fixture
async def db_engine():
    """In-memory async SQLAlchemy engine (fresh per test)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    """Session factory bound to the in-memory test engine."""
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def repository(session_factory) -> ChatHistoryRepository:
    """A ``ChatHistoryRepository`` backed by an in-memory database."""
    return ChatHistoryRepository(session_factory)


@pytest.fixture
def tool_registry() -> ToolRegistry:
    """A ``ToolRegistry`` pre-loaded with the built-in tools."""
    registry = ToolRegistry()
    registry.register(GetCurrentTimeTool())
    return registry
