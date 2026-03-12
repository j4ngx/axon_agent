"""Built-in tool: web_search.

Performs web searches using the Brave Search API via ``httpx``.
Requires the ``BRAVE_API_KEY`` environment variable to be set.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from helix.tools.base import Tool

logger = logging.getLogger(__name__)

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
_TIMEOUT = 15.0
_MAX_RESULTS = 5


class WebSearchTool(Tool):
    """Search the web using Brave Search API."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for current information. "
            "Use this when you need to find up-to-date facts, news, documentation, "
            "or any information that may not be in your training data."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "count": {
                    "type": "integer",
                    "description": f"Number of results to return (max {_MAX_RESULTS}).",
                },
            },
            "required": ["query"],
        }

    async def run(self, **kwargs: Any) -> str:
        """Execute a web search and return formatted results."""
        query: str = kwargs["query"]
        count = min(int(kwargs.get("count", _MAX_RESULTS)), _MAX_RESULTS)

        api_key = os.getenv("BRAVE_API_KEY")
        if not api_key:
            return "Error: BRAVE_API_KEY environment variable is not set."

        params = {"q": query, "count": count}
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(
                    _BRAVE_SEARCH_URL,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            logger.error("Brave Search request timed out", extra={"query": query})
            return f"Error: Search request timed out after {_TIMEOUT}s."
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Brave Search HTTP error",
                extra={"status": exc.response.status_code, "query": query},
            )
            return f"Error: Search API returned HTTP {exc.response.status_code}."
        except httpx.HTTPError as exc:
            logger.error("Brave Search request failed", extra={"error": str(exc)})
            return f"Error: Search request failed — {exc}"

        web_results = data.get("web", {}).get("results", [])
        if not web_results:
            return f"No results found for: {query}"

        lines: list[str] = [f"Search results for: {query}\n"]
        for i, result in enumerate(web_results[:count], 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            description = result.get("description", "No description")
            lines.append(f"{i}. **{title}**\n   {url}\n   {description}\n")

        return "\n".join(lines)
