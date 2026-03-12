"""Built-in tool: system_info.

Reports local system information: CPU, memory, disk, uptime, and network.
Uses only the standard library so no extra dependencies are needed.
"""

from __future__ import annotations

import os
import platform
import shutil
import time
from datetime import timedelta
from typing import Any

from helix.tools.base import Tool


def _get_uptime() -> str:
    """Return system uptime as a human-readable string (macOS / Linux)."""
    try:
        with open("/proc/uptime") as f:
            seconds = float(f.readline().split()[0])
    except FileNotFoundError:
        # macOS: use sysctl
        import subprocess

        result = subprocess.run(
            ["sysctl", "-n", "kern.boottime"],  # noqa: S607
            capture_output=True,
            text=True,
        )
        # Output like: { sec = 1717000000, usec = 0 } ...
        raw = result.stdout.strip()
        try:
            sec_part = raw.split("sec =")[1].split(",")[0].strip()
            boot_time = int(sec_part)
            seconds = time.time() - boot_time
        except (IndexError, ValueError):
            return "unknown"

    return str(timedelta(seconds=int(seconds)))


def _get_load_average() -> str:
    """Return 1/5/15 min load averages."""
    try:
        load = os.getloadavg()
        return f"{load[0]:.2f} / {load[1]:.2f} / {load[2]:.2f}"
    except OSError:
        return "unavailable"


class SystemInfoTool(Tool):
    """Report local system information."""

    @property
    def name(self) -> str:
        return "system_info"

    @property
    def description(self) -> str:
        return (
            "Get information about the local system: OS, CPU, memory, disk, uptime, "
            "and load averages. Useful for monitoring the host machine."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def run(self, **kwargs: Any) -> str:
        """Collect and return system information."""
        # Disk usage for root partition
        disk = shutil.disk_usage("/")
        disk_total_gb = disk.total / (1024**3)
        disk_used_gb = disk.used / (1024**3)
        disk_free_gb = disk.free / (1024**3)
        disk_pct = (disk.used / disk.total) * 100

        lines = [
            "**System Information**\n",
            f"- OS: {platform.system()} {platform.release()} ({platform.machine()})",
            f"- Hostname: {platform.node()}",
            f"- Python: {platform.python_version()}",
            f"- CPU cores: {os.cpu_count() or 'unknown'}",
            f"- Load avg (1/5/15 min): {_get_load_average()}",
            f"- Uptime: {_get_uptime()}",
            f"- Disk (/): {disk_used_gb:.1f} GB / {disk_total_gb:.1f} GB "
            f"({disk_pct:.0f}% used, {disk_free_gb:.1f} GB free)",
        ]

        return "\n".join(lines)
