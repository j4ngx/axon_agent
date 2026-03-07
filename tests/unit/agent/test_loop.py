"""Tests for the ``AgentLoop``."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from helix.agent.loop import _FALLBACK_RESPONSE, AgentLoop
from helix.config.settings import Settings
from helix.exceptions import LLMError
from helix.llm.base import LLMResponse, ToolCallRequest
from helix.memory.repositories import ChatHistoryRepository
from helix.tools.base import Tool
from helix.tools.registry import ToolRegistry

# ── Helpers ──────────────────────────────────────────────────────────────


class _EchoTool(Tool):
    """Dummy tool that echoes its input."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes input."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"text": {"type": "string"}}}

    async def run(self, **kwargs: Any) -> str:
        return f"echo: {kwargs.get('text', '')}"


def _make_loop(
    llm: Any,
    repository: ChatHistoryRepository,
    tool_registry: ToolRegistry,
    settings: Settings,
) -> AgentLoop:
    return AgentLoop(
        llm=llm,
        memory=repository,
        tools=tool_registry,
        settings=settings,
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestAgentLoop:
    """Unit tests for ``AgentLoop``."""

    async def test_when_llm_returns_text_expect_text_returned(
        self,
        repository: ChatHistoryRepository,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(content="Hello there!")
        loop = _make_loop(mock_llm, repository, tool_registry, settings)

        # Act
        result = await loop.run(user_id=1, user_message="Hi")

        # Assert
        assert result == "Hello there!"
        mock_llm.generate.assert_called_once()

    async def test_when_llm_fails_expect_fallback_response(
        self,
        repository: ChatHistoryRepository,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = LLMError("boom")
        loop = _make_loop(mock_llm, repository, tool_registry, settings)

        # Act
        result = await loop.run(user_id=1, user_message="Hi")

        # Assert
        assert result == _FALLBACK_RESPONSE

    async def test_when_llm_requests_tool_expect_tool_executed(
        self,
        repository: ChatHistoryRepository,
        settings: Settings,
    ) -> None:
        # Arrange
        registry = ToolRegistry()
        registry.register(_EchoTool())

        tool_call = ToolCallRequest(id="tc_1", name="echo", arguments={"text": "ping"})
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = [
            LLMResponse(content=None, tool_calls=[tool_call]),
            LLMResponse(content="Pong!"),
        ]
        loop = _make_loop(mock_llm, repository, registry, settings)

        # Act
        result = await loop.run(user_id=1, user_message="echo ping")

        # Assert
        assert result == "Pong!"
        assert mock_llm.generate.call_count == 2

    async def test_when_max_iterations_hit_expect_fallback(
        self,
        repository: ChatHistoryRepository,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        # Arrange — LLM always returns a tool call, never text.
        tool_call = ToolCallRequest(id="tc_loop", name="get_current_time", arguments={})
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(content=None, tool_calls=[tool_call])
        loop = _make_loop(mock_llm, repository, tool_registry, settings)

        # Act
        result = await loop.run(user_id=1, user_message="infinite loop")

        # Assert
        assert result == _FALLBACK_RESPONSE
        assert mock_llm.generate.call_count == settings.agent.max_iterations

    async def test_when_unknown_tool_requested_expect_error_in_context(
        self,
        repository: ChatHistoryRepository,
        settings: Settings,
    ) -> None:
        # Arrange — LLM requests a tool that doesn't exist, then gives text.
        registry = ToolRegistry()
        tool_call = ToolCallRequest(id="tc_bad", name="nonexistent", arguments={})
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = [
            LLMResponse(content=None, tool_calls=[tool_call]),
            LLMResponse(content="Fixed it."),
        ]
        loop = _make_loop(mock_llm, repository, registry, settings)

        # Act
        result = await loop.run(user_id=1, user_message="use bad tool")

        # Assert
        assert result == "Fixed it."

    async def test_when_message_sent_expect_persisted_in_memory(
        self,
        repository: ChatHistoryRepository,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(content="Saved!")
        loop = _make_loop(mock_llm, repository, tool_registry, settings)

        # Act
        await loop.run(user_id=42, user_message="remember me")

        # Assert
        history = await repository.get_recent_history(user_id=42, limit=10)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].content == "remember me"
        assert history[1].role == "assistant"
        assert history[1].content == "Saved!"
