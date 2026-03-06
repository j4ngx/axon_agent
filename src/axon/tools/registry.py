"""Tool registry — central catalogue of available tools.

The agent loop queries the registry to:

* Present the list of tools to the LLM (OpenAI function-calling schema).
* Look up and execute a tool by name when the LLM requests one.
"""

from __future__ import annotations

import logging
from typing import Any

from axon.tools.base import Tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Thread-safe, name-indexed catalogue of ``Tool`` instances.

    Example::

        registry = ToolRegistry()
        registry.register(GetCurrentTimeTool())
        tool = registry.get("get_current_time")
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._mcp_sessions: list[Any] = []

    def register(self, tool: Tool) -> None:
        """Add a tool to the registry.

        Args:
            tool: A concrete ``Tool`` instance.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        logger.info("Tool registered", extra={"tool": tool.name})

    def get(self, name: str) -> Tool | None:
        """Look up a tool by name.

        Args:
            name: The machine-readable tool name.

        Returns:
            The ``Tool`` instance, or ``None`` if not found.
        """
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Return every registered tool.

        Returns:
            A list of all ``Tool`` instances in registration order.
        """
        return list(self._tools.values())

    def get_openai_tools_schema(self) -> list[dict[str, Any]]:
        """Build the OpenAI-compatible tools array.

        Returns:
            A list of dicts ready to be passed as the ``tools`` parameter in
            a chat-completions request.
        """
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def add_mcp_session(self, session: Any) -> None:
        """Track an MCP client session for lifecycle management.

        Args:
            session: An MCP ``ClientSession`` to close on shutdown.
        """
        self._mcp_sessions.append(session)
        logger.info("MCP session tracked", extra={"total_sessions": len(self._mcp_sessions)})

    async def shutdown(self) -> None:
        """Close all tracked MCP sessions."""
        for session in self._mcp_sessions:
            try:
                await session.close()  # type: ignore[union-attr]
            except Exception:
                logger.exception("Error closing MCP session")
        self._mcp_sessions.clear()
        logger.info("Tool registry shut down")
