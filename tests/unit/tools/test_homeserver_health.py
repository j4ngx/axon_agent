"""Tests for the ``HomeserverHealthTool`` builtin tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from helix.tools.homeserver_health import HomeserverHealthTool


class TestHomeserverHealthTool:
    """Unit tests for ``HomeserverHealthTool``."""

    def setup_method(self) -> None:
        self.tool = HomeserverHealthTool()

    # -- properties -----------------------------------------------------------

    def test_when_checking_name_expect_homeserver_health(self) -> None:
        assert self.tool.name == "homeserver_health"

    def test_when_checking_description_expect_non_empty(self) -> None:
        assert len(self.tool.description) > 0

    def test_when_checking_schema_expect_empty_properties(self) -> None:
        schema = self.tool.parameters_schema
        assert schema["properties"] == {}

    def test_when_serialising_expect_valid_openai_schema(self) -> None:
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "homeserver_health"

    # -- run ------------------------------------------------------------------

    async def test_when_all_ok_expect_combined_dashboard(self) -> None:
        self.tool._docker.run = AsyncMock(return_value="🟢 **pihole** — running")
        self.tool._pihole.run = AsyncMock(return_value="**Pi-hole Summary**\n• Status: enabled")
        self.tool._uptime.run = AsyncMock(return_value="**Uptime Kuma — Service Status**")

        result = await self.tool.run()

        assert "Endurance" in result
        assert "pihole" in result
        assert "Pi-hole Summary" in result
        assert "Uptime Kuma" in result
        self.tool._docker.run.assert_awaited_once_with(command="list")
        self.tool._pihole.run.assert_awaited_once_with(command="summary")
        self.tool._uptime.run.assert_awaited_once_with(command="status")

    async def test_when_sub_tool_returns_error_expect_included(self) -> None:
        self.tool._docker.run = AsyncMock(return_value="Error: PORTAINER_URL is not configured.")
        self.tool._pihole.run = AsyncMock(return_value="**Pi-hole Summary**\n• Status: enabled")
        self.tool._uptime.run = AsyncMock(return_value="**Uptime Kuma — Service Status**")

        result = await self.tool.run()

        assert "PORTAINER_URL" in result
        assert "Pi-hole Summary" in result

    async def test_when_sub_tool_raises_expect_graceful_fallback(self) -> None:
        self.tool._docker.run = AsyncMock(side_effect=RuntimeError("unexpected"))
        self.tool._pihole.run = AsyncMock(return_value="**Pi-hole Summary**")
        self.tool._uptime.run = AsyncMock(return_value="**Uptime Kuma**")

        with patch("helix.tools.homeserver_health.logger") as mock_logger:
            result = await self.tool.run()

        assert "Docker check failed" in result
        assert "Pi-hole Summary" in result
        mock_logger.error.assert_called_once()

    async def test_when_all_sub_tools_fail_expect_all_errors(self) -> None:
        self.tool._docker.run = AsyncMock(side_effect=RuntimeError("docker down"))
        self.tool._pihole.run = AsyncMock(side_effect=RuntimeError("pihole down"))
        self.tool._uptime.run = AsyncMock(side_effect=RuntimeError("kuma down"))

        result = await self.tool.run()

        assert "Endurance" in result
        assert "Docker check failed" in result
        assert "Pi-hole check failed" in result
        assert "Uptime Kuma check failed" in result
