"""Fallback LLM client — tries the primary backend first, then the fallback.

The agent loop receives an instance of ``FallbackLLMClient`` and never knows
which backend actually served the request.
"""

from __future__ import annotations

import logging
from typing import Any

from helix.exceptions import LLMError
from helix.llm.base import LLMClient, LLMResponse

logger = logging.getLogger(__name__)


class FallbackLLMClient:
    """Wraps a primary and a fallback ``LLMClient``.

    On every call to ``generate()`` the primary backend is tried first.
    If it raises ``LLMError``, a single retry is attempted against the
    fallback backend.

    Args:
        primary: The preferred LLM client (e.g. Groq).
        fallback: The backup LLM client (e.g. OpenRouter).
    """

    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        self._primary = primary
        self._fallback = fallback

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Generate a response, falling back on failure.

        Args:
            messages: OpenAI-style message list.
            tools: Optional OpenAI-style tool definitions.

        Returns:
            A normalised ``LLMResponse`` from whichever backend succeeded.

        Raises:
            LLMError: If **both** the primary and fallback backends fail.
        """
        try:
            return await self._primary.generate(messages, tools)
        except LLMError as primary_exc:
            logger.warning(
                "Primary LLM failed, switching to fallback",
                extra={"error": str(primary_exc)},
            )
            try:
                return await self._fallback.generate(messages, tools)
            except LLMError as fallback_exc:
                logger.error(
                    "Fallback LLM also failed",
                    extra={"error": str(fallback_exc)},
                )
                raise LLMError(
                    f"Both LLM backends failed. Primary: {primary_exc} | Fallback: {fallback_exc}"
                ) from fallback_exc
