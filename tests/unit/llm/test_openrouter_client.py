"""Tests for the ``OpenRouterLLMClient``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from axon.exceptions import LLMError
from axon.llm.openrouter_client import OpenRouterLLMClient


class TestOpenRouterParseResponse:
    """Unit tests for ``OpenRouterLLMClient._parse_response``."""

    def test_when_valid_text_response_expect_content(self) -> None:
        data = {
            "choices": [
                {
                    "message": {
                        "content": "Hello!",
                        "tool_calls": None,
                    }
                }
            ]
        }
        result = OpenRouterLLMClient._parse_response(data)
        assert result.content == "Hello!"
        assert result.tool_calls == []

    def test_when_valid_tool_calls_expect_parsed(self) -> None:
        data = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "get_time",
                                    "arguments": '{"tz": "UTC"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        result = OpenRouterLLMClient._parse_response(data)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_time"
        assert result.tool_calls[0].arguments == {"tz": "UTC"}

    def test_when_tool_args_already_dict_expect_passthrough(self) -> None:
        data = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_2",
                                "function": {
                                    "name": "echo",
                                    "arguments": {"text": "hi"},
                                },
                            }
                        ],
                    }
                }
            ]
        }
        result = OpenRouterLLMClient._parse_response(data)
        assert result.tool_calls[0].arguments == {"text": "hi"}

    def test_when_empty_choices_expect_llm_error(self) -> None:
        with pytest.raises(LLMError, match="Failed to parse"):
            OpenRouterLLMClient._parse_response({"choices": []})

    def test_when_missing_choices_key_expect_llm_error(self) -> None:
        with pytest.raises(LLMError, match="Failed to parse"):
            OpenRouterLLMClient._parse_response({})

    def test_when_missing_message_key_expect_llm_error(self) -> None:
        with pytest.raises(LLMError, match="Failed to parse"):
            OpenRouterLLMClient._parse_response({"choices": [{"index": 0}]})

    def test_when_malformed_json_args_expect_llm_error(self) -> None:
        data = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_3",
                                "function": {
                                    "name": "test",
                                    "arguments": "{invalid json",
                                },
                            }
                        ],
                    }
                }
            ]
        }
        with pytest.raises(LLMError, match="Failed to parse"):
            OpenRouterLLMClient._parse_response(data)

    def test_when_no_tool_calls_key_expect_empty_list(self) -> None:
        data = {
            "choices": [
                {
                    "message": {
                        "content": "plain reply",
                    }
                }
            ]
        }
        result = OpenRouterLLMClient._parse_response(data)
        assert result.content == "plain reply"
        assert result.tool_calls == []


class TestOpenRouterGenerate:
    """Integration-level tests for ``OpenRouterLLMClient.generate``."""

    async def test_when_http_error_expect_llm_error(self) -> None:
        client = OpenRouterLLMClient(api_key="fake-key")
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        client._client = AsyncMock()
        client._client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with pytest.raises(LLMError, match="OpenRouter HTTP"):
            await client.generate([{"role": "user", "content": "hi"}])

    async def test_when_request_error_expect_llm_error(self) -> None:
        client = OpenRouterLLMClient(api_key="fake-key")
        client._client = AsyncMock()
        client._client.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))

        with pytest.raises(LLMError, match="OpenRouter request error"):
            await client.generate([{"role": "user", "content": "hi"}])

    async def test_when_close_expect_client_closed(self) -> None:
        client = OpenRouterLLMClient(api_key="fake-key")
        client._client = AsyncMock()

        await client.close()

        client._client.aclose.assert_called_once()
