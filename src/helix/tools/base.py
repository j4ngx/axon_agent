"""Abstract base class for all Helix tools.

To add a new tool:

1. Create a new module under ``helix/tools/``.
2. Subclass ``Tool`` and implement ``name``, ``description``,
   ``parameters_schema``, and ``run()``.
3. Register it in ``helix/tools/registry.py`` (or dynamically at startup).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Contract that every Helix tool must satisfy.

    Subclasses are automatically usable in the agent loop once registered
    with :class:`helix.tools.registry.ToolRegistry`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique machine-readable tool name (e.g. ``"get_current_time"``)."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Short, human-readable description shown to the LLM."""

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema describing the tool's input parameters.

        Return an empty-properties object if the tool takes no arguments::

            {"type": "object", "properties": {}}
        """

    @abstractmethod
    async def run(self, **kwargs: Any) -> str:
        """Execute the tool and return a textual result.

        Args:
            **kwargs: Keyword arguments matching ``parameters_schema``.

        Returns:
            A string the LLM can consume as a tool observation.
        """

    def to_openai_schema(self) -> dict[str, Any]:
        """Serialise this tool into an OpenAI function-calling schema.

        Returns:
            A dict suitable for inclusion in the ``tools`` parameter of a
            chat-completions request.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
