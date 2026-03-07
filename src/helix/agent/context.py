"""Agent context — lightweight state container for a single agent invocation.

The context is built from conversation history and is passed through each
iteration of the agent loop.  It is **not** persisted — it exists only for
the duration of one user-message processing cycle.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Mutable state container for a single agent invocation.

    Attributes:
        user_id: Telegram user ID whose message is being processed.
        messages: OpenAI-style message list (system + history + current).
        max_iterations: Maximum number of think/act/observe cycles.
    """

    user_id: int
    messages: list[dict[str, Any]] = Field(default_factory=list)
    max_iterations: int = 5
