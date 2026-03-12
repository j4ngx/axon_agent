"""Tests for the ``UrlFetchTool`` builtin tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx

from helix.tools.url_fetch import UrlFetchTool, _html_to_text, _is_private_url


class TestHtmlToText:
    """Unit tests for the HTML-to-text helper."""

    def test_when_plain_text_expect_unchanged(self) -> None:
        assert _html_to_text("hello world") == "hello world"

    def test_when_html_tags_expect_stripped(self) -> None:
        assert "bold" in _html_to_text("<b>bold</b> text")
        assert "<b>" not in _html_to_text("<b>bold</b> text")

    def test_when_script_tags_expect_removed(self) -> None:
        html = "<p>hello</p><script>alert('xss')</script><p>world</p>"
        result = _html_to_text(html)
        assert "alert" not in result
        assert "hello" in result
        assert "world" in result

    def test_when_entities_expect_decoded(self) -> None:
        assert "&" in _html_to_text("&amp;")
        assert "<" in _html_to_text("&lt;")


class TestIsPrivateUrl:
    """Unit tests for the SSRF mitigation helper."""

    def test_when_localhost_expect_true(self) -> None:
        assert _is_private_url("http://localhost:8080/api") is True

    def test_when_loopback_expect_true(self) -> None:
        assert _is_private_url("http://127.0.0.1/secret") is True

    def test_when_private_192_expect_true(self) -> None:
        assert _is_private_url("http://192.168.1.1/admin") is True

    def test_when_private_10_expect_true(self) -> None:
        assert _is_private_url("http://10.0.0.1/") is True

    def test_when_public_url_expect_false(self) -> None:
        assert _is_private_url("https://example.com/page") is False

    def test_when_ftp_scheme_expect_true(self) -> None:
        assert _is_private_url("ftp://example.com/file") is True

    def test_when_file_scheme_expect_true(self) -> None:
        assert _is_private_url("file:///etc/passwd") is True


class TestUrlFetchTool:
    """Unit tests for ``UrlFetchTool``."""

    def setup_method(self) -> None:
        self.tool = UrlFetchTool()

    def test_when_checking_name_expect_url_fetch(self) -> None:
        assert self.tool.name == "url_fetch"

    def test_when_checking_description_expect_non_empty_string(self) -> None:
        assert isinstance(self.tool.description, str)
        assert len(self.tool.description) > 0

    def test_when_checking_parameters_schema_expect_url_required(self) -> None:
        schema = self.tool.parameters_schema
        assert "url" in schema["properties"]
        assert "url" in schema["required"]

    def test_when_serialising_expect_valid_openai_schema(self) -> None:
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "url_fetch"

    async def test_when_private_url_expect_error(self) -> None:
        result = await self.tool.run(url="http://localhost:8080/secret")
        assert "Error" in result
        assert "private" in result.lower()

    async def test_when_fetch_html_expect_text_extraction(self) -> None:
        mock_response = AsyncMock()
        mock_response.text = "<html><body><p>Hello World</p></body></html>"
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.raise_for_status = lambda: None

        with patch("helix.tools.url_fetch.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.tool.run(url="https://example.com")

        assert "Hello World" in result
        assert "<p>" not in result

    async def test_when_fetch_json_expect_raw_response(self) -> None:
        mock_response = AsyncMock()
        mock_response.text = '{"key": "value"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = lambda: None

        with patch("helix.tools.url_fetch.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.tool.run(url="https://api.example.com/data")

        assert '"key"' in result

    async def test_when_timeout_expect_error_message(self) -> None:
        with patch("helix.tools.url_fetch.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.tool.run(url="https://slow.example.com")

        assert "timed out" in result

    async def test_when_content_exceeds_limit_expect_truncated(self) -> None:
        long_text = "x" * 20000
        mock_response = AsyncMock()
        mock_response.text = long_text
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.raise_for_status = lambda: None

        with patch("helix.tools.url_fetch.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.tool.run(url="https://example.com/long")

        assert "truncated" in result
