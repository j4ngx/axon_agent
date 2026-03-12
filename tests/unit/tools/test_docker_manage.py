"""Tests for the ``DockerManageTool`` builtin tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from helix.tools.docker_manage import DockerManageTool, _parse_docker_logs

# ---------------------------------------------------------------------------
# Helper: reusable mock httpx client factory
# ---------------------------------------------------------------------------


def _mock_client(response: MagicMock | None = None, side_effect: Exception | None = None):
    """Return a patched ``httpx.AsyncClient`` context-manager mock."""
    client = AsyncMock()
    if side_effect:
        client.get.side_effect = side_effect
        client.post.side_effect = side_effect
    elif response is not None:
        client.get.return_value = response
        client.post.return_value = response
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _json_response(data, status_code: int = 200):
    """Create a MagicMock that behaves like an httpx.Response."""
    resp = MagicMock()
    resp.json.return_value = data
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# _parse_docker_logs tests
# ---------------------------------------------------------------------------


class TestParseDockerLogs:
    """Tests for the Docker multiplexed log parser."""

    def test_when_valid_frames_expect_text(self) -> None:
        # stdout frame: type=1, size=5, payload="hello"
        frame = b"\x01\x00\x00\x00\x00\x00\x00\x05hello"
        assert _parse_docker_logs(frame) == "hello"

    def test_when_multiple_frames_expect_concatenated(self) -> None:
        frame1 = b"\x01\x00\x00\x00\x00\x00\x00\x03foo"
        frame2 = b"\x02\x00\x00\x00\x00\x00\x00\x03bar"
        assert _parse_docker_logs(frame1 + frame2) == "foobar"

    def test_when_empty_input_expect_empty_string(self) -> None:
        assert _parse_docker_logs(b"") == ""

    def test_when_no_valid_frames_expect_raw_decode(self) -> None:
        # Less than 8 bytes — fallback to raw decode
        assert _parse_docker_logs(b"plain") == "plain"


# ---------------------------------------------------------------------------
# DockerManageTool tests
# ---------------------------------------------------------------------------

_CONTAINERS = [
    {
        "Id": "abc123",
        "Names": ["/endurance-pihole"],
        "State": "running",
        "Status": "Up 3 days",
        "Image": "pihole/pihole:2024.07.0",
    },
    {
        "Id": "def456",
        "Names": ["/endurance-portainer"],
        "State": "exited",
        "Status": "Exited (0) 2 hours ago",
        "Image": "portainer/portainer-ce:2.27.3",
    },
]

_ENV = {"PORTAINER_URL": "http://portainer:9000", "PORTAINER_API_TOKEN": "test-token"}


class TestDockerManageTool:
    """Unit tests for ``DockerManageTool``."""

    def setup_method(self) -> None:
        self.tool = DockerManageTool()

    # -- property tests -------------------------------------------------------

    def test_when_checking_name_expect_docker_manage(self) -> None:
        assert self.tool.name == "docker_manage"

    def test_when_checking_description_expect_non_empty(self) -> None:
        assert len(self.tool.description) > 0

    def test_when_checking_schema_expect_command_required(self) -> None:
        schema = self.tool.parameters_schema
        assert "command" in schema["properties"]
        assert "command" in schema["required"]

    def test_when_serialising_expect_valid_openai_schema(self) -> None:
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "docker_manage"

    # -- env validation -------------------------------------------------------

    @patch.dict("os.environ", {}, clear=True)
    async def test_when_no_portainer_url_expect_error(self) -> None:
        result = await self.tool.run(command="list")
        assert "PORTAINER_URL" in result

    @patch.dict("os.environ", {"PORTAINER_URL": "http://p:9000"}, clear=True)
    async def test_when_no_api_token_expect_error(self) -> None:
        result = await self.tool.run(command="list")
        assert "PORTAINER_API_TOKEN" in result

    @patch.dict("os.environ", _ENV)
    async def test_when_lifecycle_without_container_expect_error(self) -> None:
        result = await self.tool.run(command="start")
        assert "container" in result.lower()

    # -- list -----------------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_list_expect_formatted_containers(self) -> None:
        resp = _json_response(_CONTAINERS)
        client = _mock_client(resp)

        with patch("helix.tools.docker_manage.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="list")

        assert "endurance-pihole" in result
        assert "endurance-portainer" in result
        assert "🟢" in result
        assert "🔴" in result

    @patch.dict("os.environ", _ENV)
    async def test_when_list_empty_expect_message(self) -> None:
        resp = _json_response([])
        client = _mock_client(resp)

        with patch("helix.tools.docker_manage.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="list")

        assert "No containers" in result

    @patch.dict("os.environ", _ENV)
    async def test_when_list_http_error_expect_error(self) -> None:
        client = _mock_client(side_effect=httpx.ConnectError("connection refused"))

        with patch("helix.tools.docker_manage.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="list")

        assert "Error" in result

    # -- lifecycle (start/stop/restart) ---------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_restart_container_expect_success(self) -> None:
        list_resp = _json_response(_CONTAINERS)
        action_resp = MagicMock()
        action_resp.raise_for_status = MagicMock()

        client = AsyncMock()
        client.get.return_value = list_resp
        client.post.return_value = action_resp
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("helix.tools.docker_manage.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="restart", container="endurance-pihole")

        assert "✅" in result
        assert "restart" in result

    @patch.dict("os.environ", _ENV)
    async def test_when_container_not_found_expect_error(self) -> None:
        list_resp = _json_response([])
        client = _mock_client(list_resp)

        with patch("helix.tools.docker_manage.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="stop", container="nonexistent")

        assert "not found" in result

    # -- logs -----------------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_logs_expect_formatted_output(self) -> None:
        list_resp = _json_response(_CONTAINERS)
        log_resp = MagicMock()
        log_resp.content = b"\x01\x00\x00\x00\x00\x00\x00\x0btest log 1\n"
        log_resp.raise_for_status = MagicMock()

        client = AsyncMock()
        # First call = resolve ID, second call = get logs
        client.get.side_effect = [list_resp, log_resp]
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("helix.tools.docker_manage.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="logs", container="endurance-pihole")

        assert "Logs" in result
        assert "test log" in result

    # -- stats ----------------------------------------------------------------

    @patch.dict("os.environ", _ENV)
    async def test_when_stats_expect_cpu_and_memory(self) -> None:
        list_resp = _json_response(_CONTAINERS)
        stats_data = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 200_000_000},
                "system_cpu_usage": 1_000_000_000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100_000_000},
                "system_cpu_usage": 900_000_000,
            },
            "memory_stats": {
                "usage": 50 * 1024 * 1024,  # 50 MB
                "limit": 1024 * 1024 * 1024,  # 1 GB
            },
        }
        stats_resp = _json_response(stats_data)

        client = AsyncMock()
        client.get.side_effect = [list_resp, stats_resp]
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("helix.tools.docker_manage.httpx.AsyncClient", return_value=client):
            result = await self.tool.run(command="stats", container="endurance-pihole")

        assert "CPU" in result
        assert "Memory" in result
        assert "50.0 MB" in result
