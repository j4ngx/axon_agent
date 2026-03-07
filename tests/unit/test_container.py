"""Tests for the DI ``Container``."""

from __future__ import annotations

import pytest

from helix.config.settings import (
    AgentConfig,
    LLMConfig,
    LoggingConfig,
    MemoryConfig,
    Settings,
    SkillConfig,
)
from helix.di.container import Container


@pytest.fixture
def container_settings(tmp_path) -> Settings:
    """Settings suitable for DI container integration tests."""
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("You are a test assistant.")
    return Settings(
        telegram_bot_token="123456789:AAFake-Token_ForUnitTestsOnly",
        telegram_allowed_user_ids=[12345],
        groq_api_key="gsk_test_fake_key_for_unit_tests",
        openrouter_api_key="sk-or-v1-test_fake_key",
        llm=LLMConfig(),
        agent=AgentConfig(max_iterations=2, history_limit=5, system_prompt_path=str(prompt_file)),
        memory=MemoryConfig(project_id="test-project"),
        logging=LoggingConfig(level="DEBUG"),
        skills=[SkillConfig(name="get_current_time", type="builtin", enabled=True)],
    )


class TestContainer:
    """Unit tests for the DI ``Container``."""

    async def test_when_init_expect_all_services_available(
        self, container_settings: Settings, mocker: pytest.FixtureRequest
    ) -> None:
        mocker.patch("helix.di.container.init_firebase")
        container = Container(container_settings)
        await container.init()

        try:
            assert container.settings is container_settings
            assert container.memory is not None
            assert container.llm is not None
            assert container.tools is not None
            assert container.agent is not None
            assert container.bot is not None
            assert container.dispatcher is not None
        finally:
            await container.shutdown()

    async def test_when_shutdown_expect_engine_disposed(
        self, container_settings: Settings, mocker: pytest.FixtureRequest
    ) -> None:
        mocker.patch("helix.di.container.init_firebase")
        container = Container(container_settings)
        await container.init()
        await container.shutdown()

        # After shutdown the engine should be disposed (no error on double-shutdown).
        await container.shutdown()

    async def test_when_accessing_before_init_expect_assertion_error(
        self, container_settings: Settings
    ) -> None:
        container = Container(container_settings)
        with pytest.raises(AssertionError, match="not initialised"):
            _ = container.memory

    async def test_when_skills_configured_expect_tools_registered(
        self, container_settings: Settings, mocker: pytest.FixtureRequest
    ) -> None:
        mocker.patch("helix.di.container.init_firebase")
        container = Container(container_settings)
        await container.init()

        try:
            tools = container.tools.list_tools()
            names = [t.name for t in tools]
            assert "get_current_time" in names
        finally:
            await container.shutdown()
