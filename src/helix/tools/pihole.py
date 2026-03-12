"""Built-in tool: pihole.

Query and control Pi-hole DNS ad blocker via its Admin API.
Requires ``PIHOLE_URL`` environment variable.  ``PIHOLE_API_TOKEN`` is
needed for read-protected and write operations.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from helix.tools.base import Tool

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


def _sanitize_error(exc: Exception, token: str) -> str:
    """Remove the API token from error messages to prevent leakage."""
    msg = str(exc)
    if token:
        msg = msg.replace(token, "***")
    return msg


class PiholeTool(Tool):
    """Query and control Pi-hole DNS ad blocker."""

    @property
    def name(self) -> str:
        return "pihole"

    @property
    def description(self) -> str:
        return (
            "Interact with the Pi-hole DNS ad blocker on the homeserver. "
            "Get blocking statistics, view top blocked domains, recent queries, "
            "and enable or disable ad-blocking temporarily."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": [
                        "summary",
                        "top_blocked",
                        "recent_blocked",
                        "recent_queries",
                        "enable",
                        "disable",
                    ],
                    "description": "Pi-hole action to perform.",
                },
                "count": {
                    "type": "integer",
                    "description": (
                        "Number of items for top_blocked / recent_queries (default 10)."
                    ),
                },
                "duration": {
                    "type": "integer",
                    "description": (
                        "Seconds to disable blocking (for 'disable' command, default 300)."
                    ),
                },
            },
            "required": ["command"],
        }

    async def run(self, **kwargs: Any) -> str:
        command: str = kwargs["command"]
        count: int = kwargs.get("count", 10)
        duration: int = kwargs.get("duration", 300)

        base_url = os.getenv("PIHOLE_URL", "").rstrip("/")
        token = os.getenv("PIHOLE_API_TOKEN", "")

        if not base_url:
            return "Error: PIHOLE_URL is not configured."

        dispatch = {
            "summary": self._summary,
            "top_blocked": self._top_blocked,
            "recent_blocked": self._recent_blocked,
            "recent_queries": self._recent_queries,
            "enable": self._enable,
            "disable": self._disable,
        }
        handler = dispatch.get(command)
        if not handler:
            return f"Error: Unknown command '{command}'."

        return await handler(base_url=base_url, token=token, count=count, duration=duration)

    async def _api(self, base_url: str, params: str) -> httpx.Response:
        url = f"{base_url}/admin/api.php?{params}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp

    # -- commands -------------------------------------------------------------

    async def _summary(self, base_url: str, **_: Any) -> str:
        try:
            resp = await self._api(base_url, "summary")
            d = resp.json()
        except httpx.HTTPError as exc:
            logger.error("Pi-hole summary failed", extra={"error": str(exc)})
            return f"Error: {_sanitize_error(exc, '')}"
        except ValueError:
            return "Error: Invalid response from Pi-hole."
        return (
            "**Pi-hole Summary**\n"
            f"• Domains on blocklist: {d.get('domains_being_blocked', 'N/A')}\n"
            f"• DNS queries today: {d.get('dns_queries_today', 'N/A')}\n"
            f"• Ads blocked today: {d.get('ads_blocked_today', 'N/A')}\n"
            f"• Ads percentage: {d.get('ads_percentage_today', 'N/A')}%\n"
            f"• Unique domains: {d.get('unique_domains', 'N/A')}\n"
            f"• Queries forwarded: {d.get('queries_forwarded', 'N/A')}\n"
            f"• Queries cached: {d.get('queries_cached', 'N/A')}\n"
            f"• Status: {d.get('status', 'N/A')}"
        )

    async def _top_blocked(self, base_url: str, token: str, count: int = 10, **_: Any) -> str:
        if not token:
            return "Error: PIHOLE_API_TOKEN required for top_blocked."
        count = max(1, min(count, 50))
        try:
            resp = await self._api(base_url, f"topItems={count}&auth={token}")
            data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("Pi-hole top_blocked failed", extra={"error": _sanitize_error(exc, token)})
            return f"Error: {_sanitize_error(exc, token)}"
        except ValueError:
            return "Error: Invalid response from Pi-hole."
        blocked = data.get("top_ads", {})
        if not blocked:
            return "No blocked domains found."

        lines = [f"**Top {count} Blocked Domains**\n"]
        for domain, hits in list(blocked.items())[:count]:
            lines.append(f"• `{domain}` — {hits} hits")
        return "\n".join(lines)

    async def _recent_blocked(self, base_url: str, **_: Any) -> str:
        try:
            resp = await self._api(base_url, "recentBlocked")
        except httpx.HTTPError as exc:
            logger.error("Pi-hole recent_blocked failed", extra={"error": str(exc)})
            return f"Error: {_sanitize_error(exc, '')}"
        return f"**Most recently blocked:** `{resp.text}`"

    async def _recent_queries(
        self,
        base_url: str,
        token: str,
        count: int = 10,
        **_: Any,
    ) -> str:
        if not token:
            return "Error: PIHOLE_API_TOKEN required for recent_queries."
        count = max(1, min(count, 100))
        try:
            resp = await self._api(base_url, f"getAllQueries={count}&auth={token}")
            data = resp.json()
        except httpx.HTTPError as exc:
            logger.error(
                "Pi-hole recent_queries failed", extra={"error": _sanitize_error(exc, token)}
            )
            return f"Error: {_sanitize_error(exc, token)}"
        except ValueError:
            return "Error: Invalid response from Pi-hole."

        queries = data.get("data", [])
        if not queries:
            return "No recent queries found."

        lines = [f"**Recent DNS Queries** (last {len(queries)})\n"]
        for q in queries[:count]:
            if len(q) >= 4:
                domain = q[2]
                requester = q[3]
                try:
                    status_code = int(q[4]) if len(q) > 4 else 0
                except (ValueError, TypeError):
                    status_code = 0
                status = "✅" if status_code in (1, 2, 3) else "🚫"
                lines.append(f"{status} `{domain}` ← {requester}")
        return "\n".join(lines)

    async def _enable(self, base_url: str, token: str, **_: Any) -> str:
        if not token:
            return "Error: PIHOLE_API_TOKEN required to enable blocking."
        try:
            resp = await self._api(base_url, f"enable&auth={token}")
            status = resp.json().get("status", "unknown")
        except httpx.HTTPError as exc:
            logger.error("Pi-hole enable failed", extra={"error": _sanitize_error(exc, token)})
            return f"Error: {_sanitize_error(exc, token)}"
        except ValueError:
            return "Error: Invalid response from Pi-hole."
        return f"✅ Pi-hole blocking **{status}**."

    async def _disable(
        self,
        base_url: str,
        token: str,
        duration: int = 300,
        **_: Any,
    ) -> str:
        if not token:
            return "Error: PIHOLE_API_TOKEN required to disable blocking."
        duration = max(0, min(duration, 86400))
        try:
            resp = await self._api(base_url, f"disable={duration}&auth={token}")
            status = resp.json().get("status", "unknown")
        except httpx.HTTPError as exc:
            logger.error("Pi-hole disable failed", extra={"error": _sanitize_error(exc, token)})
            return f"Error: {_sanitize_error(exc, token)}"
        except ValueError:
            return "Error: Invalid response from Pi-hole."
        return f"⏸️ Pi-hole blocking **{status}** for {duration}s."
