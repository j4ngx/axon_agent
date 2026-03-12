"""Groq LLM client — primary backend.

Uses the official ``groq`` Python SDK which provides an async client
that mirrors the OpenAI chat-completions interface.
"""

from __future__ import annotations

import logging
from typing import Any

from groq import APIError, AsyncGroq, BadRequestError, RateLimitError

from helix.exceptions import LLMError, LLMRateLimitError, LLMToolUseError
from helix.llm.base import LLMResponse, ToolCallRequest

logger = logging.getLogger(__name__)


class GroqLLMClient:
    """Groq chat-completions client.

    Args:
        api_key: Groq API key.
        model: Model identifier (e.g. ``"llama-3.3-70b-versatile"``).
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        timeout: float = 30.0,
    ) -> None:
        self._client = AsyncGroq(api_key=api_key, timeout=timeout)
        self._model = model

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to Groq.

        Args:
            messages: OpenAI-style message list.
            tools: Optional OpenAI-style tool definitions.

        Returns:
            A normalised ``LLMResponse``.

        Raises:
            LLMError: If the Groq API returns an error or the request times out.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        logger.info(
            "Groq request",
            extra={"model": self._model, "message_count": len(messages)},
        )

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except RateLimitError as exc:
            logger.warning("Groq rate limit hit", extra={"error": str(exc)})
            raise LLMRateLimitError(f"Groq rate limit: {exc}") from exc
        except BadRequestError as exc:
            error_body = getattr(exc, "body", {}) or {}
            error_info = error_body.get("error", {}) if isinstance(error_body, dict) else {}
            if error_info.get("code") == "tool_use_failed":
                logger.warning(
                    "Groq tool_use_failed — LLM generated malformed tool call",
                    extra={"failed_generation": error_info.get("failed_generation", "")[:200]},
                )
                raise LLMToolUseError(f"Groq tool_use_failed: {exc}") from exc
            logger.error(
                "Groq bad request",
                extra={"status": getattr(exc, 'status_code', None), "error": str(exc)},
            )
            raise LLMError(f"Groq bad request: {exc}") from exc
        except APIError as exc:
            logger.error(
                "Groq API error",
                extra={"status": getattr(exc, 'status_code', None), "error": str(exc)},
            )
            status = getattr(exc, 'status_code', '?')
            raise LLMError(
                f"Groq API error (status={status}): {exc}"
            ) from exc
        except Exception as exc:
            logger.error(
                "Groq unexpected error",
                extra={"error_type": type(exc).__name__, "error": str(exc)},
            )
            raise LLMError(f"Groq error ({type(exc).__name__}): {exc}") from exc

        choice = response.choices[0]
        tool_calls = [
            ToolCallRequest.from_openai_tool_call(tc) for tc in (choice.message.tool_calls or [])
        ]

        return LLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
        )
