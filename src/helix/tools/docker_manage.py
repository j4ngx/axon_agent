"""Built-in tool: docker_manage.

Manages Docker containers on the homeserver via the Portainer API.
Requires ``PORTAINER_URL`` and ``PORTAINER_API_TOKEN`` environment variables.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from helix.tools.base import Tool

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0
_ENDPOINT_ID = 1  # Default Portainer local environment


def _parse_docker_logs(raw: bytes) -> str:
    """Parse Docker multiplexed log stream into plain text.

    Docker log streams contain 8-byte headers per frame:
    byte 0 = stream type (1=stdout, 2=stderr), bytes 4-7 = payload size.
    """
    result: list[str] = []
    i = 0
    while i + 8 <= len(raw):
        size = int.from_bytes(raw[i + 4 : i + 8], "big")
        i += 8
        end = min(i + size, len(raw))
        result.append(raw[i:end].decode("utf-8", errors="replace"))
        i = end
    if not result:
        return raw.decode("utf-8", errors="replace")
    return "".join(result)


class DockerManageTool(Tool):
    """Manage Docker containers on the homeserver via Portainer."""

    @property
    def name(self) -> str:
        return "docker_manage"

    @property
    def description(self) -> str:
        return (
            "Manage Docker containers on the Endurance homeserver. "
            "List running containers, start/stop/restart services, "
            "view container logs, and check resource usage."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["list", "start", "stop", "restart", "logs", "stats"],
                    "description": "Action to perform on Docker containers.",
                },
                "container": {
                    "type": "string",
                    "description": (
                        "Container name (e.g. 'endurance-pihole'). "
                        "Required for start, stop, restart, logs, stats."
                    ),
                },
                "tail": {
                    "type": "integer",
                    "description": "Number of log lines to return (default 50, max 200).",
                },
            },
            "required": ["command"],
        }

    async def run(self, **kwargs: Any) -> str:
        command: str = kwargs["command"]
        container: str = kwargs.get("container", "")
        tail: int = kwargs.get("tail", 50)

        base_url = os.getenv("PORTAINER_URL", "").rstrip("/")
        api_token = os.getenv("PORTAINER_API_TOKEN", "")

        if not base_url:
            return "Error: PORTAINER_URL is not configured."
        if not api_token:
            return "Error: PORTAINER_API_TOKEN is not configured."

        if command in ("start", "stop", "restart", "logs", "stats") and not container:
            return f"Error: 'container' is required for '{command}'."

        dispatch = {
            "list": self._list,
            "start": self._lifecycle,
            "stop": self._lifecycle,
            "restart": self._lifecycle,
            "logs": self._logs,
            "stats": self._stats,
        }
        handler = dispatch.get(command)
        if not handler:
            return f"Error: Unknown command '{command}'."

        return await handler(
            base_url=base_url,
            token=api_token,
            command=command,
            container=container,
            tail=tail,
        )

    # -- helpers --------------------------------------------------------------

    async def _get(
        self,
        client: httpx.AsyncClient,
        url: str,
        token: str,
    ) -> httpx.Response:
        return await client.get(url, headers={"X-API-Key": token})

    async def _post(
        self,
        client: httpx.AsyncClient,
        url: str,
        token: str,
    ) -> httpx.Response:
        return await client.post(url, headers={"X-API-Key": token})

    async def _resolve_id(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        token: str,
        name: str,
    ) -> str:
        """Resolve container name to Docker container ID."""
        url = f"{base_url}/api/endpoints/{_ENDPOINT_ID}/docker/containers/json?all=true"
        resp = await self._get(client, url, token)
        resp.raise_for_status()
        for c in resp.json():
            names = [n.lstrip("/") for n in (c.get("Names") or [])]
            cid = c.get("Id", "")
            if name in names or cid.startswith(name):
                return cid
        return ""

    # -- command handlers -----------------------------------------------------

    async def _list(self, base_url: str, token: str, **_: Any) -> str:
        url = f"{base_url}/api/endpoints/{_ENDPOINT_ID}/docker/containers/json?all=true"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await self._get(client, url, token)
                resp.raise_for_status()
                containers = resp.json()
        except httpx.HTTPError as exc:
            logger.error("Portainer list failed", extra={"error": str(exc)})
            return f"Error: {exc}"
        except ValueError:
            return "Error: Invalid response from Portainer."
        if not containers:
            return "No containers found."

        lines = [f"**Docker Containers** ({len(containers)})\n"]
        for c in containers:
            name = (c.get("Names") or ["/unknown"])[0].lstrip("/")
            state = c.get("State", "unknown")
            status = c.get("Status", "")
            image = c.get("Image", "")
            emoji = "🟢" if state == "running" else "🔴" if state == "exited" else "🟡"
            lines.append(f"{emoji} **{name}** — {state} ({status})\n   `{image}`")
        return "\n".join(lines)

    async def _lifecycle(
        self,
        base_url: str,
        token: str,
        command: str,
        container: str,
        **_: Any,
    ) -> str:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                cid = await self._resolve_id(client, base_url, token, container)
                if not cid:
                    return f"Error: Container '{container}' not found."
                url = f"{base_url}/api/endpoints/{_ENDPOINT_ID}/docker/containers/{cid}/{command}"
                resp = await self._post(client, url, token)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Portainer lifecycle failed",
                extra={
                    "command": command,
                    "container": container,
                    "status": exc.response.status_code,
                },
            )
            return f"Error: {command} '{container}' \u2014 HTTP {exc.response.status_code}"
        except httpx.HTTPError as exc:
            logger.error(
                "Portainer lifecycle failed",
                extra={"command": command, "container": container, "error": str(exc)},
            )
            return f"Error: {command} '{container}' — {exc}"
        return f"✅ **{container}** — `{command}` executed."

    async def _logs(
        self,
        base_url: str,
        token: str,
        container: str,
        tail: int = 50,
        **_: Any,
    ) -> str:
        tail = max(1, min(tail, 200))
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                cid = await self._resolve_id(client, base_url, token, container)
                if not cid:
                    return f"Error: Container '{container}' not found."
                url = (
                    f"{base_url}/api/endpoints/{_ENDPOINT_ID}"
                    f"/docker/containers/{cid}/logs"
                    f"?stdout=true&stderr=true&tail={tail}"
                )
                resp = await self._get(client, url, token)
                resp.raise_for_status()
                content = resp.content
        except httpx.HTTPError as exc:
            logger.error(
                "Portainer logs failed",
                extra={"container": container, "error": str(exc)},
            )
            return f"Error: logs '{container}' \u2014 {exc}"

        text = _parse_docker_logs(content)
        if len(text) > 4000:
            text = "[… truncated]\n" + text[-4000:]

        return f"**Logs — {container}** (last {tail} lines):\n```\n{text}\n```"

    async def _stats(
        self,
        base_url: str,
        token: str,
        container: str,
        **_: Any,
    ) -> str:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                cid = await self._resolve_id(client, base_url, token, container)
                if not cid:
                    return f"Error: Container '{container}' not found."
                url = (
                    f"{base_url}/api/endpoints/{_ENDPOINT_ID}"
                    f"/docker/containers/{cid}/stats?stream=false"
                )
                resp = await self._get(client, url, token)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.error(
                "Portainer stats failed",
                extra={"container": container, "error": str(exc)},
            )
            return f"Error: stats '{container}' \u2014 {exc}"
        except ValueError:
            return f"Error: Invalid stats response for '{container}'."

        # CPU calculation
        cpu_delta = data.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0) - data.get(
            "precpu_stats", {}
        ).get("cpu_usage", {}).get("total_usage", 0)
        sys_delta = data.get("cpu_stats", {}).get("system_cpu_usage", 0) - data.get(
            "precpu_stats", {}
        ).get("system_cpu_usage", 0)
        online_cpus = data.get("cpu_stats", {}).get("online_cpus") or len(
            data.get("cpu_stats", {}).get("cpu_usage", {}).get("percpu_usage") or [1]
        )
        cpu_pct = (cpu_delta / sys_delta * online_cpus * 100) if sys_delta > 0 else 0.0

        # Memory calculation
        mem_usage = data.get("memory_stats", {}).get("usage", 0)
        mem_limit = data.get("memory_stats", {}).get("limit", 1)
        mem_mb = mem_usage / (1024 * 1024)
        mem_pct = (mem_usage / mem_limit * 100) if mem_limit > 0 else 0.0

        return (
            f"**Stats — {container}**\n"
            f"• CPU: {cpu_pct:.1f}%\n"
            f"• Memory: {mem_mb:.1f} MB ({mem_pct:.1f}%)"
        )
