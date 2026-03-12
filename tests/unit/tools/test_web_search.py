"""Tests for the ``WebSearchTool`` builtin tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from helix.tools.web_search import WebSearchTool


class TestWebSearchTool:
    """Unit tests for ``WebSearchTool``."""

    def setup_method(self) -> None:
        self.tool = WebSearchTool()

    def test_when_checking_name_expect_web_search(self) -> None:
        assert self.tool.name == "web_search"

    def test_when_checking_description_expect_non_empty_string(self) -> None:
        assert isinstance(self.tool.description, str)
        assert len(self.tool.description) > 0

    def test_when_checking_parameters_schema_expect_query_required(self) -> None:
        schema = self.tool.parameters_schema
        assert "query" in schema["properties"]
        assert "query" in schema["required"]

    def test_when_serialising_expect_valid_openai_schema(self) -> None:
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "web_search"

    @patch.dict("os.environ", {}, clear=True)
    async def test_when_no_api_key_expect_error_message(self) -> None:
        result = await self.tool.run(query="test")
        assert "BRAVE_API_KEY" in result
        assert "Error" in result

    @patch.dict("os.environ", {"BRAVE_API_KEY": "test-key"})
    async def test_when_search_succeeds_expect_formatted_results(self) -> None:
        mock_response_data = {
            "web": {
                "results": [
                    {
                        "title": "Result One",
                        "url": "https://example.com/one",
                        "description": "First result description.",
                    },
                    {
                        "title": "Result Two",
                        "url": "https://example.com/two",
                        "description": "Second result description.",
                    },
                ]
            }
        }

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch("helix.tools.web_search.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.tool.run(query="python asyncio")

        assert "Result One" in result
        assert "Result Two" in result
        assert "example.com" in result

    @patch.dict("os.environ", {"BRAVE_API_KEY": "test-key"})
    async def test_when_no_results_expect_no_results_message(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("helix.tools.web_search.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.tool.run(query="xyznonexistent")

        assert "No results" in result

    @patch.dict("os.environ", {"BRAVE_API_KEY": "test-key"})
    async def test_when_timeout_expect_error_message(self) -> None:
        with patch("helix.tools.web_search.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.tool.run(query="test")

        assert "timed out" in result

    @patch.dict("os.environ", {"BRAVE_API_KEY": "test-key"})
    async def test_when_http_error_expect_status_in_error(self) -> None:
        mock_response = AsyncMock()
        mock_response.status_code = 429

        with patch("helix.tools.web_search.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "rate limited",
                request=httpx.Request("GET", "https://example.com"),
                response=mock_response,
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.tool.run(query="test")

        assert "429" in result
