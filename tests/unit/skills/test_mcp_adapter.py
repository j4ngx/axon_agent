"""Tests for the ``MCPToolAdapter``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from axon.skills.mcp_adapter import MCPToolAdapter


class TestMCPToolAdapter:
    """Unit tests for ``MCPToolAdapter``."""

    def _make_adapter(
        self,
        session: AsyncMock | None = None,
        tool_name: str = "test_tool",
        tool_description: str = "A test MCP tool",
        input_schema: dict | None = None,
    ) -> MCPToolAdapter:
        """Build an adapter with a mocked session and tool descriptor."""
        mock_session = session or AsyncMock()
        mock_tool = MagicMock()
        mock_tool.name = tool_name
        mock_tool.description = tool_description
        mock_tool.inputSchema = input_schema or {"type": "object", "properties": {}}
        return MCPToolAdapter(session=mock_session, mcp_tool=mock_tool, skill_name="test_skill")

    def test_when_checking_name_expect_mcp_tool_name(self) -> None:
        adapter = self._make_adapter(tool_name="my_tool")
        assert adapter.name == "my_tool"

    def test_when_checking_description_expect_mcp_description(self) -> None:
        adapter = self._make_adapter(tool_description="Does something")
        assert adapter.description == "Does something"

    def test_when_no_description_expect_fallback(self) -> None:
        adapter = self._make_adapter(tool_description=None)
        assert "MCP tool" in adapter.description
        assert "test_skill" in adapter.description

    def test_when_checking_schema_expect_input_schema(self) -> None:
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        adapter = self._make_adapter(input_schema=schema)
        assert adapter.parameters_schema == schema

    def test_when_no_schema_expect_empty_object(self) -> None:
        adapter = self._make_adapter(input_schema=None)
        # Force inputSchema to None
        adapter._mcp_tool.inputSchema = None
        assert adapter.parameters_schema == {"type": "object", "properties": {}}

    async def test_when_run_success_expect_text_returned(self) -> None:
        # Arrange
        mock_session = AsyncMock()
        text_block = MagicMock()
        text_block.text = "result text"
        mock_result = MagicMock()
        mock_result.content = [text_block]
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        adapter = self._make_adapter(session=mock_session)

        # Act
        result = await adapter.run(param="value")

        # Assert
        assert result == "result text"
        mock_session.call_tool.assert_called_once_with("test_tool", arguments={"param": "value"})

    async def test_when_run_multiple_blocks_expect_joined(self) -> None:
        # Arrange
        mock_session = AsyncMock()
        block1 = MagicMock()
        block1.text = "line1"
        block2 = MagicMock()
        block2.text = "line2"
        mock_result = MagicMock()
        mock_result.content = [block1, block2]
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        adapter = self._make_adapter(session=mock_session)

        # Act
        result = await adapter.run()

        # Assert
        assert result == "line1\nline2"

    async def test_when_run_empty_content_expect_no_output(self) -> None:
        # Arrange
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.content = []
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        adapter = self._make_adapter(session=mock_session)

        # Act
        result = await adapter.run()

        # Assert
        assert result == "(no output)"

    async def test_when_run_raises_expect_error_string(self) -> None:
        # Arrange
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(side_effect=RuntimeError("connection lost"))

        adapter = self._make_adapter(session=mock_session)

        # Act
        result = await adapter.run()

        # Assert
        assert "MCP tool error" in result
        assert "connection lost" in result
