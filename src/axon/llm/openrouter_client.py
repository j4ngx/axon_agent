"""OpenRouter LLM client — fallback backend.

Talks to the OpenRouter REST API (OpenAI-compatible) using ``httpx``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from axon.exceptions import LLMError
from axon.llm.base import LLMResponse, ToolCallRequest

logger = logging.getLogger(__name__)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLMClient:
    """OpenRouter chat-completions client.

    Args:
        api_key: OpenRouter API key.
        model: Model identifier (e.g. ``"meta-llama/llama-3.3-70b-instruct:free"``).
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=timeout)

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to OpenRouter.

        Args:
            messages: OpenAI-style message list.
            tools: Optional OpenAI-style tool definitions.

        Returns:
            A normalised ``LLMResponse``.

        Raises:
            LLMError: If the request fails or the response cannot be parsed.
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/j4ngx/axon",
            "X-Title": "Axon",
        }

        logger.info(
            "OpenRouter request",
            extra={"model": self._model, "message_count": len(messages)},
        )

        try:
            resp = await self._client.post(
                f"{_OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "OpenRouter HTTP error",
                extra={"status": exc.response.status_code, "body": exc.response.text[:500]},
            )
            raise LLMError(f"OpenRouter HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("OpenRouter request error", extra={"error": str(exc)})
            raise LLMError(f"OpenRouter request error: {exc}") from exc

        return self._parse_response(data)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> LLMResponse:
        """Parse a raw OpenRouter JSON response into an ``LLMResponse``.

        Args:
            data: The raw JSON response dict.

        Returns:
            A normalised ``LLMResponse``.

        Raises:
            LLMError: If the response structure is unexpected.
        """
        try:
            choice = data["choices"][0]
            message = choice["message"]

            tool_calls: list[ToolCallRequest] = []
            for tc in message.get("tool_calls") or []:
                raw_args = tc["function"]["arguments"]
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                tool_calls.append(
                    ToolCallRequest(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=arguments,
                    )
                )

            return LLMResponse(
                content=message.get("content"),
                tool_calls=tool_calls,
            )
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise LLMError(f"Failed to parse OpenRouter response: {exc}") from exc
