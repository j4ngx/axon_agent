"""Fallback LLM client — tries the primary backend first, then the fallback.

The agent loop receives an instance of ``FallbackLLMClient`` and never knows
which backend actually served the request.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from helix.exceptions import LLMError, LLMRateLimitError, LLMToolUseError
from helix.llm.base import LLMClient, LLMResponse

logger = logging.getLogger(__name__)

_RATE_LIMIT_DELAYS = (2, 5, 10)  # seconds — up to 3 retries


class FallbackLLMClient:
    """Wraps a primary and an optional fallback ``LLMClient``.

    On every call to ``generate()`` the primary backend is tried first.
    If it raises ``LLMError`` and a fallback is configured, a single retry
    is attempted against the fallback backend.

    Args:
        primary: The preferred LLM client (e.g. Groq).
        fallback: The backup LLM client (e.g. OpenRouter), or ``None``.
    """

    def __init__(self, primary: LLMClient, fallback: LLMClient | None = None) -> None:
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
            LLMError: If the primary (and optional fallback) backends fail.
            LLMToolUseError: Re-raised immediately so the agent loop can retry
                without tools.
        """
        try:
            return await self._call_with_rate_limit_retry(self._primary, messages, tools)
        except LLMToolUseError:
            # Let the agent loop handle this — retrying on a different backend
            # with the same tools is unlikely to help.
            raise
        except LLMError as primary_exc:
            if self._fallback is None:
                logger.error(
                    "Primary LLM failed and no fallback is configured",
                    extra={"error": str(primary_exc)},
                )
                raise

            logger.warning(
                "Primary LLM failed, switching to fallback",
                extra={"error": str(primary_exc)},
            )
            try:
                return await self._call_with_rate_limit_retry(
                    self._fallback, messages, tools
                )
            except LLMError as fallback_exc:
                logger.error(
                    "Fallback LLM also failed",
                    extra={"error": str(fallback_exc)},
                )
                raise LLMError(
                    f"Both LLM backends failed. Primary: {primary_exc} | Fallback: {fallback_exc}"
                ) from fallback_exc

    @staticmethod
    async def _call_with_rate_limit_retry(
        client: LLMClient,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> LLMResponse:
        """Call a client, retrying a few times on rate-limit errors."""
        for attempt, delay in enumerate(_RATE_LIMIT_DELAYS):
            try:
                return await client.generate(messages, tools)
            except LLMRateLimitError:
                logger.warning(
                    "Rate-limited, retrying",
                    extra={"attempt": attempt + 1, "delay_s": delay},
                )
                await asyncio.sleep(delay)
        # Final attempt — let the error propagate.
        return await client.generate(messages, tools)
