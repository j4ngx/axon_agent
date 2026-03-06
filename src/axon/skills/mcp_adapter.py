"""MCP tool adapter — wraps an MCP server tool as an Axon ``Tool``.

This adapter bridges the MCP (Model Context Protocol) tool interface with
Axon's internal ``Tool`` ABC, so MCP-provided tools are indistinguishable
from built-in tools from the agent loop's perspective.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from axon.tools.base import Tool

logger = logging.getLogger(__name__)


class MCPToolAdapter(Tool):
    """Adapt an MCP tool into an Axon ``Tool``.

    Args:
        session: An active ``ClientSession`` connected to the MCP server.
        mcp_tool: The tool descriptor returned by ``session.list_tools()``.
        skill_name: The parent skill name (for logging / namespacing).
    """

    def __init__(self, session: Any, mcp_tool: Any, skill_name: str) -> None:
        self._session = session
        self._mcp_tool = mcp_tool
        self._skill_name = skill_name

    @property
    def name(self) -> str:
        """Return the MCP tool's name."""
        return self._mcp_tool.name

    @property
    def description(self) -> str:
        """Return the MCP tool's description."""
        return self._mcp_tool.description or f"MCP tool from {self._skill_name}"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Return the MCP tool's input schema.

        Falls back to an empty-object schema if the tool doesn't declare one.
        """
        schema = getattr(self._mcp_tool, "inputSchema", None)
        if schema and isinstance(schema, dict):
            return schema
        return {"type": "object", "properties": {}}

    async def run(self, **kwargs: Any) -> str:
        """Execute the MCP tool via the session and return the result.

        Args:
            **kwargs: Arguments matching the tool's ``parameters_schema``.

        Returns:
            A string representation of the tool's output.
        """
        logger.info(
            "Calling MCP tool",
            extra={"tool": self.name, "skill": self._skill_name},
        )
        try:
            result = await self._session.call_tool(self.name, arguments=kwargs)
            # MCP returns a list of content blocks; join their text.
            parts: list[str] = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                else:
                    parts.append(json.dumps(block.model_dump(), default=str))
            return "\n".join(parts) if parts else "(no output)"
        except Exception as exc:
            logger.exception("MCP tool call failed", extra={"tool": self.name})
            return f"MCP tool error: {exc}"
