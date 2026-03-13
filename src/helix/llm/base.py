"""Common interface and DTOs for LLM backends.

All concrete LLM clients implement the ``LLMClient`` protocol so the agent
loop never knows (or cares) which backend is being used.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Data-transfer objects
# ---------------------------------------------------------------------------


class ToolCallRequest(BaseModel):
    """A tool invocation requested by the LLM.

    Attributes:
        id: Unique identifier for this tool call (used in followup messages).
        name: The tool name the LLM wants to invoke.
        arguments: Parsed JSON arguments for the tool.
    """

    id: str
    name: str
    arguments: dict[str, Any]

    @classmethod
    def from_openai_tool_call(cls, tool_call: Any) -> ToolCallRequest:
        """Construct from an OpenAI-compatible tool-call object.

        Args:
            tool_call: A tool-call object with ``id``, ``function.name``,
                and ``function.arguments`` (JSON string).

        Returns:
            A ``ToolCallRequest`` instance.
        """
        raw_args = tool_call.function.arguments
        if raw_args is None:
            arguments: dict[str, Any] = {}
        elif isinstance(raw_args, str):
            parsed = json.loads(raw_args) if raw_args.strip() else {}
            arguments = parsed if isinstance(parsed, dict) else {}
        else:
            arguments = raw_args if isinstance(raw_args, dict) else {}
        return cls(
            id=tool_call.id,
            name=tool_call.function.name,
            arguments=arguments,
        )


class LLMResponse(BaseModel):
    """Normalised response from any LLM backend.

    Attributes:
        content: The assistant's text reply (may be ``None`` when tool calls
            are present).
        tool_calls: Zero or more tool invocations requested by the LLM.
    """

    content: str | None = None
    tool_calls: list[ToolCallRequest] = []


# ---------------------------------------------------------------------------
# Protocol (structural subtyping)
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMClient(Protocol):
    """Minimal contract that every LLM backend must satisfy."""

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request and return a normalised response.

        Args:
            messages: OpenAI-style message list.
            tools: Optional OpenAI-style tool definitions.

        Returns:
            A normalised ``LLMResponse``.
        """
        ...
