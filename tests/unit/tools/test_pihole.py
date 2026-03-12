"""Tests for the ``PiholeTool`` builtin tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from helix.tools.pihole import PiholeTool


def _mock_client(response: MagicMock | None = None, side_effect: Exception | None = None):
    client = AsyncMock()
    if side_effect:
        client.get.side_effect = side_effect
    elif response is not None:
        client.get.return_value = response
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _json_response(data, text: str = ""):
    resp = MagicMock()
    resp.json.return_value = data
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


_ENV = {"PIHOLE_URL": "http://pihole:80", "PIHOLE_API_TOKEN": "test-token"}
_ENV_NO_TOKEN = {"PIHOLE_URL": "http://pihole:80"}


class TestPiholeTool:
    """Unit tests for ``PiholeTool``."""

    def setup_method(self) -> None:
        self.tool = PiholeTool()

    # -- properties -----------------------------------------------------------

    def test_when_checking_name_expect_pihole(self) -> None:
        assert self.tool.name == "pihole"

    def test_when_checking_description_expect_non_empty(self) -> None:
        assert len(self.tool.description) > 0

    def test_when_checking_schema_expect_command_required(self) -> None:
        schema = self.tool.parameters_schema
        assert "command" in schema["properties"]
        assert "command" in schema["required"]

    def test_when_serialising_expect_valid_openai_schema(self) -> None:
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "pihole"

    # -- env validation -------------------------------------------------------

    @patch.dict("os.environ", {}, clear=True)
    async def test_when_no_pihole_url_expect_error(self) -> None:
        result = await self.tool.run(command="summary")
        assert "PIHOLE_URL" in result

    # -- summary --------------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_summary_expect_formatted_stats(self) -> None:
        data = {
            "domains_being_blocked": "150,000",
            "dns_queries_today": "12,345",
            "ads_blocked_today": "2,345",
            "ads_percentage_today": "19.0",
            "unique_domains": "4,567",
            "queries_forwarded": "8,000",
            "queries_cached": "2,000",
            "status": "enabled",
        }
        resp = _json_response(data)
        client = _mock_client(resp)

        with patch("helix.tools.pihole.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="summary")

        assert "Pi-hole Summary" in result
        assert "150,000" in result
        assert "12,345" in result
        assert "enabled" in result

    @patch.dict("os.environ", _ENV)
    async def test_when_summary_http_error_expect_error(self) -> None:
        client = _mock_client(side_effect=httpx.ConnectError("refused"))

        with patch("helix.tools.pihole.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="summary")

        assert "Error" in result

    # -- top_blocked ----------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_top_blocked_expect_domains(self) -> None:
        data = {"top_ads": {"ads.example.com": 500, "tracker.io": 300}}
        resp = _json_response(data)
        client = _mock_client(resp)

        with patch("helix.tools.pihole.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="top_blocked")

        assert "ads.example.com" in result
        assert "500" in result

    @patch.dict("os.environ", _ENV_NO_TOKEN, clear=True)
    async def test_when_top_blocked_no_token_expect_error(self) -> None:
        result = await self.tool.run(command="top_blocked")
        assert "PIHOLE_API_TOKEN" in result

    # -- recent_blocked -------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_recent_blocked_expect_domain(self) -> None:
        resp = _json_response({}, text="blocked.example.com")
        client = _mock_client(resp)

        with patch("helix.tools.pihole.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="recent_blocked")

        assert "blocked.example.com" in result

    # -- recent_queries -------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_recent_queries_expect_formatted(self) -> None:
        data = {
            "data": [
                ["1710000000", "A", "example.com", "192.168.1.10", "2", "0", "0"],
                ["1710000001", "AAAA", "blocked.ad", "192.168.1.10", "5", "0", "0"],
            ]
        }
        resp = _json_response(data)
        client = _mock_client(resp)

        with patch("helix.tools.pihole.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="recent_queries")

        assert "example.com" in result
        assert "blocked.ad" in result

    @patch.dict("os.environ", _ENV_NO_TOKEN, clear=True)
    async def test_when_recent_queries_no_token_expect_error(self) -> None:
        result = await self.tool.run(command="recent_queries")
        assert "PIHOLE_API_TOKEN" in result

    # -- enable / disable -----------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_enable_expect_success(self) -> None:
        resp = _json_response({"status": "enabled"})
        client = _mock_client(resp)

        with patch("helix.tools.pihole.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="enable")

        assert "✅" in result
        assert "enabled" in result

    @patch.dict("os.environ", _ENV)
    async def test_when_disable_expect_success(self) -> None:
        resp = _json_response({"status": "disabled"})
        client = _mock_client(resp)

        with patch("helix.tools.pihole.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="disable", duration=600)

        assert "⏸️" in result
        assert "disabled" in result

    @patch.dict("os.environ", _ENV_NO_TOKEN, clear=True)
    async def test_when_enable_no_token_expect_error(self) -> None:
        result = await self.tool.run(command="enable")
        assert "PIHOLE_API_TOKEN" in result

    @patch.dict("os.environ", _ENV_NO_TOKEN, clear=True)
    async def test_when_disable_no_token_expect_error(self) -> None:
        result = await self.tool.run(command="disable")
        assert "PIHOLE_API_TOKEN" in result

    # -- unknown command ------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_unknown_command_expect_error(self) -> None:
        result = await self.tool.run(command="nope")
        assert "Unknown command" in result
