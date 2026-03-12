"""Built-in tool: homeserver_health.

Aggregated health dashboard for the Endurance homeserver.
Combines Docker container status, Pi-hole stats, and Uptime Kuma
monitoring into a single unified view.
"""

from __future__ import annotations

import logging
from typing import Any

from helix.tools.base import Tool
from helix.tools.docker_manage import DockerManageTool
from helix.tools.pihole import PiholeTool
from helix.tools.uptime_monitor import UptimeMonitorTool

logger = logging.getLogger(__name__)


class HomeserverHealthTool(Tool):
    """Unified homeserver health dashboard."""

    def __init__(self) -> None:
        self._docker = DockerManageTool()
        self._pihole = PiholeTool()
        self._uptime = UptimeMonitorTool()

    @property
    def name(self) -> str:
        return "homeserver_health"

    @property
    def description(self) -> str:
        return (
            "Get a unified health overview of the Endurance homeserver. "
            "Shows Docker container status, Pi-hole blocking stats, "
            "and Uptime Kuma service monitoring in a single dashboard."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def run(self, **kwargs: Any) -> str:
        sections: list[str] = ["**🏠 Endurance — Health Dashboard**\n"]

        for label, tool, cmd in [
            ("Docker", self._docker, "list"),
            ("Pi-hole", self._pihole, "summary"),
            ("Uptime Kuma", self._uptime, "status"),
        ]:
            try:
                result = await tool.run(command=cmd)
            except Exception as exc:
                logger.error("Health sub-tool failed", extra={"tool": label, "error": str(exc)})
                result = f"Error: {label} check failed — {exc}"
            sections.append(result)
            sections.append("")

        return "\n".join(sections).rstrip()
