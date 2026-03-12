"""Tests for the ``UptimeMonitorTool`` builtin tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from helix.tools.uptime_monitor import UptimeMonitorTool


def _mock_client(responses: list[MagicMock] | None = None, side_effect=None):
    """Create a mock httpx.AsyncClient.

    *responses* - list of mock responses for sequential ``client.get()`` calls.
    """
    client = AsyncMock()
    if side_effect:
        client.get.side_effect = side_effect
    elif responses:
        client.get.side_effect = responses
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _json_response(data):
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


_ENV = {"UPTIME_KUMA_URL": "http://kuma:3001", "UPTIME_KUMA_SLUG": "endurance"}

_STATUS_DATA = {
    "publicGroupList": [
        {
            "name": "Core Services",
            "monitorList": [
                {"id": 1, "name": "Portainer"},
                {"id": 2, "name": "Pi-hole"},
            ],
        }
    ]
}

_HEARTBEAT_DATA = {
    "heartbeatList": {
        "1": [{"status": 1, "ping": 12, "msg": ""}],
        "2": [{"status": 0, "ping": 0, "msg": "Connection refused"}],
    },
    "uptimeList": {
        "1_24": 0.999,
        "1_720": 0.998,
        "2_24": 0.85,
        "2_720": 0.90,
    },
}


class TestUptimeMonitorTool:
    """Unit tests for ``UptimeMonitorTool``."""

    def setup_method(self) -> None:
        self.tool = UptimeMonitorTool()

    # -- properties -----------------------------------------------------------

    def test_when_checking_name_expect_uptime_monitor(self) -> None:
        assert self.tool.name == "uptime_monitor"

    def test_when_checking_description_expect_non_empty(self) -> None:
        assert len(self.tool.description) > 0

    def test_when_checking_schema_expect_command_required(self) -> None:
        schema = self.tool.parameters_schema
        assert "command" in schema["properties"]
        assert "command" in schema["required"]

    def test_when_serialising_expect_valid_openai_schema(self) -> None:
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "uptime_monitor"

    # -- env validation -------------------------------------------------------

    @patch.dict("os.environ", {}, clear=True)
    async def test_when_no_url_expect_error(self) -> None:
        result = await self.tool.run(command="status")
        assert "UPTIME_KUMA_URL" in result

    # -- status ---------------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_status_expect_formatted_monitors(self) -> None:
        status_resp = _json_response(_STATUS_DATA)
        hb_resp = _json_response(_HEARTBEAT_DATA)
        client = _mock_client(responses=[status_resp, hb_resp])

        with patch("helix.tools.uptime_monitor.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="status")

        assert "Uptime Kuma" in result
        assert "Portainer" in result
        assert "Pi-hole" in result
        assert "🟢 UP" in result
        assert "🔴 DOWN" in result

    @patch.dict("os.environ", _ENV)
    async def test_when_status_no_groups_expect_no_monitors(self) -> None:
        status_resp = _json_response({"publicGroupList": []})
        hb_resp = _json_response({"heartbeatList": {}})
        client = _mock_client(responses=[status_resp, hb_resp])

        with patch("helix.tools.uptime_monitor.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="status")

        assert "No monitors found" in result

    @patch.dict("os.environ", _ENV)
    async def test_when_status_http_error_expect_error(self) -> None:
        client = _mock_client(side_effect=httpx.ConnectError("refused"))

        with patch("helix.tools.uptime_monitor.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="status")

        assert "Error" in result

    # -- heartbeat ------------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_heartbeat_expect_detailed_data(self) -> None:
        status_resp = _json_response(_STATUS_DATA)
        hb_resp = _json_response(_HEARTBEAT_DATA)
        client = _mock_client(responses=[status_resp, hb_resp])

        with patch("helix.tools.uptime_monitor.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="heartbeat")

        assert "Heartbeat Details" in result
        assert "Portainer" in result
        assert "12ms" in result
        assert "99.9%" in result
        assert "Connection refused" in result

    @patch.dict("os.environ", _ENV)
    async def test_when_heartbeat_empty_expect_no_data(self) -> None:
        status_resp = _json_response({"publicGroupList": []})
        hb_resp = _json_response({"heartbeatList": {}, "uptimeList": {}})
        client = _mock_client(responses=[status_resp, hb_resp])

        with patch("helix.tools.uptime_monitor.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="heartbeat")

        assert "No heartbeat data" in result

    @patch.dict("os.environ", _ENV)
    async def test_when_heartbeat_http_error_expect_error(self) -> None:
        client = _mock_client(side_effect=httpx.ConnectError("timeout"))

        with patch("helix.tools.uptime_monitor.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="heartbeat")

        assert "Error" in result

    # -- unknown command ------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_unknown_command_expect_error(self) -> None:
        result = await self.tool.run(command="nope")
        assert "Unknown command" in result
