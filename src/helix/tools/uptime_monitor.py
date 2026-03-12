"""Built-in tool: uptime_monitor.

Monitor service uptime via Uptime Kuma's public status-page API.
Requires ``UPTIME_KUMA_URL`` environment variable.  The status page slug
defaults to ``"endurance"`` and can be changed via ``UPTIME_KUMA_SLUG``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from helix.tools.base import Tool

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_STATUS_LABELS = {0: "🔴 DOWN", 1: "🟢 UP", 2: "🟡 PENDING", 3: "🔧 MAINTENANCE"}


class UptimeMonitorTool(Tool):
    """Monitor service uptime via Uptime Kuma."""

    @property
    def name(self) -> str:
        return "uptime_monitor"

    @property
    def description(self) -> str:
        return (
            "Check the uptime status of homeserver services via Uptime Kuma. "
            "View current status of all monitors or detailed heartbeat data "
            "with uptime percentages and response times."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["status", "heartbeat"],
                    "description": (
                        "'status' — overview of all monitors. "
                        "'heartbeat' — detailed uptime percentages and response times."
                    ),
                },
            },
            "required": ["command"],
        }

    async def run(self, **kwargs: Any) -> str:
        command: str = kwargs["command"]

        base_url = os.getenv("UPTIME_KUMA_URL", "").rstrip("/")
        slug = os.getenv("UPTIME_KUMA_SLUG", "endurance")

        if not base_url:
            return "Error: UPTIME_KUMA_URL is not configured."

        if command == "status":
            return await self._status(base_url, slug)
        if command == "heartbeat":
            return await self._heartbeat(base_url, slug)

        return f"Error: Unknown command '{command}'."

    # -- commands -------------------------------------------------------------

    async def _status(self, base_url: str, slug: str) -> str:
        """Get an overview of all monitors from the status page."""
        try:
            status_data, hb_data = await self._fetch_data(base_url, slug)
        except httpx.HTTPError as exc:
            logger.error("Uptime Kuma status failed", extra={"error": str(exc)})
            return f"Error: Could not reach Uptime Kuma — {exc}"
        except ValueError:
            return "Error: Invalid response from Uptime Kuma."

        groups = status_data.get("publicGroupList", [])
        if not groups:
            return "No monitors found on the status page."

        # Build a monitor_id → latest status mapping from heartbeat data
        hb_list = hb_data.get("heartbeatList", {})
        latest_status: dict[int, int] = {}
        for mid, beats in hb_list.items():
            if beats:
                latest_status[int(mid)] = beats[-1].get("status", -1)

        lines = ["**Uptime Kuma — Service Status**\n"]
        for group in groups:
            group_name = group.get("name", "Services")
            lines.append(f"**{group_name}**")
            for monitor in group.get("monitorList", []):
                name = monitor.get("name", "Unknown")
                mid = monitor.get("id", 0)
                status_code = latest_status.get(mid, -1)
                status_str = _STATUS_LABELS.get(status_code, "❓ UNKNOWN")
                lines.append(f"  {status_str} {name}")
            lines.append("")

        return "\n".join(lines).rstrip()

    async def _heartbeat(self, base_url: str, slug: str) -> str:
        """Get detailed heartbeat data with uptime percentages."""
        try:
            status_data, hb_data = await self._fetch_data(base_url, slug)
        except httpx.HTTPError as exc:
            logger.error("Uptime Kuma heartbeat failed", extra={"error": str(exc)})
            return f"Error: Could not reach Uptime Kuma — {exc}"
        except ValueError:
            return "Error: Invalid response from Uptime Kuma."

        hb_list = hb_data.get("heartbeatList", {})
        uptime_list = hb_data.get("uptimeList", {})

        if not hb_list:
            return "No heartbeat data available."

        # Build monitor_id → name mapping from status page data
        id_to_name: dict[int, str] = {}
        for group in status_data.get("publicGroupList", []):
            for monitor in group.get("monitorList", []):
                id_to_name[monitor.get("id", 0)] = monitor.get("name", "Unknown")

        lines = ["**Uptime Kuma — Heartbeat Details**\n"]
        for monitor_id, beats in hb_list.items():
            if not beats:
                continue
            mid = int(monitor_id)
            latest = beats[-1]
            status_code = latest.get("status", -1)
            status_str = _STATUS_LABELS.get(status_code, "❓ UNKNOWN")
            ping = latest.get("ping", 0)
            msg = latest.get("msg", "")
            name = id_to_name.get(mid, f"Monitor #{mid}")

            uptime_24h = uptime_list.get(f"{mid}_24", 0)
            uptime_30d = uptime_list.get(f"{mid}_720", 0)

            lines.append(
                f"{status_str} **{name}**\n"
                f"  Ping: {ping}ms | "
                f"24h: {uptime_24h * 100:.1f}% | "
                f"30d: {uptime_30d * 100:.1f}%"
            )
            if msg:
                lines.append(f"  Message: {msg}")
            lines.append("")

        return "\n".join(lines).rstrip() if len(lines) > 1 else "No heartbeat data available."

    # -- helpers --------------------------------------------------------------

    async def _fetch_data(self, base_url: str, slug: str) -> tuple[dict, dict]:
        """Fetch both status page config and heartbeat data."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            status_resp = await client.get(f"{base_url}/api/status-page/{slug}")
            status_resp.raise_for_status()
            hb_resp = await client.get(f"{base_url}/api/status-page/heartbeat/{slug}")
            hb_resp.raise_for_status()
        return status_resp.json(), hb_resp.json()  # ValueError propagates on bad JSON
