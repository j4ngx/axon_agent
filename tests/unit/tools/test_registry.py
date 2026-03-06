"""Tests for the ``ToolRegistry``."""

from __future__ import annotations

from typing import Any

import pytest

from axon.tools.base import Tool
from axon.tools.registry import ToolRegistry


class _DummyTool(Tool):
    """Minimal concrete tool for testing the registry."""

    def __init__(self, tool_name: str = "dummy") -> None:
        self._name = tool_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "A dummy tool for tests."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"x": {"type": "string"}}}

    async def run(self, **kwargs: Any) -> str:
        return f"dummy result: {kwargs}"


class TestToolRegistry:
    """Unit tests for ``ToolRegistry``."""

    def setup_method(self) -> None:
        """Create a fresh registry for each test."""
        self.registry = ToolRegistry()

    def test_when_registering_tool_expect_it_retrievable_by_name(self) -> None:
        tool = _DummyTool("my_tool")
        self.registry.register(tool)
        assert self.registry.get("my_tool") is tool

    def test_when_getting_unknown_tool_expect_none(self) -> None:
        assert self.registry.get("nonexistent") is None

    def test_when_registering_duplicate_expect_value_error(self) -> None:
        self.registry.register(_DummyTool("dup"))
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(_DummyTool("dup"))

    def test_when_listing_tools_expect_all_registered(self) -> None:
        self.registry.register(_DummyTool("a"))
        self.registry.register(_DummyTool("b"))
        names = [t.name for t in self.registry.list_tools()]
        assert names == ["a", "b"]

    def test_when_empty_registry_expect_empty_list(self) -> None:
        assert self.registry.list_tools() == []

    def test_when_getting_openai_schema_expect_valid_structure(self) -> None:
        self.registry.register(_DummyTool("t1"))
        schemas = self.registry.get_openai_tools_schema()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "t1"

    def test_when_adding_mcp_session_expect_tracked(self) -> None:
        mock_session = object()
        self.registry.add_mcp_session(mock_session)
        assert len(self.registry._mcp_sessions) == 1

    async def test_when_shutdown_expect_sessions_cleared(self) -> None:
        class _FakeSession:
            closed = False

            async def close(self) -> None:
                self.closed = True

        session = _FakeSession()
        self.registry.add_mcp_session(session)
        await self.registry.shutdown()

        assert session.closed
        assert len(self.registry._mcp_sessions) == 0
