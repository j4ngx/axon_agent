"""Built-in tool: url_fetch.

Fetches a URL and extracts readable text content using ``httpx``.
Strips HTML to produce clean text the LLM can consume directly.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any

import httpx

from helix.tools.base import Tool

logger = logging.getLogger(__name__)

_TIMEOUT = 20.0
_MAX_CONTENT_LENGTH = 8000  # characters


def _html_to_text(raw_html: str) -> str:
    """Lightweight HTML → plain text conversion without extra dependencies."""
    # Remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block tags with newlines
    text = re.sub(r"<(?:br|p|div|h[1-6]|li|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode entities
    text = html.unescape(text)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class UrlFetchTool(Tool):
    """Fetch and extract readable text from a URL."""

    @property
    def name(self) -> str:
        return "url_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch a webpage or API endpoint and return its text content. "
            "For HTML pages, strips tags and returns readable text. "
            "For JSON/text endpoints, returns the raw response."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch.",
                },
            },
            "required": ["url"],
        }

    async def run(self, **kwargs: Any) -> str:
        """Fetch the URL and return extracted text."""
        url: str = kwargs["url"]

        # Basic SSRF protection: block private/internal addresses
        if _is_private_url(url):
            return "Error: Fetching private/internal URLs is not allowed."

        headers = {
            "User-Agent": "Helix-Agent/0.1 (url-fetch tool)",
            "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.8",
        }

        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                follow_redirects=True,
                max_redirects=5,
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException:
            logger.error("URL fetch timed out", extra={"url": url})
            return f"Error: Request timed out after {_TIMEOUT}s."
        except httpx.TooManyRedirects:
            return "Error: Too many redirects."
        except httpx.HTTPStatusError as exc:
            return f"Error: HTTP {exc.response.status_code}"
        except httpx.HTTPError as exc:
            logger.error("URL fetch failed", extra={"url": url, "error": str(exc)})
            return f"Error: Request failed — {exc}"

        content_type = response.headers.get("content-type", "")
        body = response.text

        if "html" in content_type:
            body = _html_to_text(body)

        # Truncate to avoid overwhelming the LLM context
        if len(body) > _MAX_CONTENT_LENGTH:
            body = body[:_MAX_CONTENT_LENGTH] + "\n\n[… content truncated]"

        return body


def _is_private_url(url: str) -> bool:
    """Reject URLs pointing to private/loopback addresses (SSRF mitigation)."""
    import urllib.parse

    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return True

    hostname = (parsed.hostname or "").lower()

    # Block common private patterns
    private_patterns = [
        "localhost",
        "127.",
        "10.",
        "192.168.",
        "172.16.",
        "172.17.",
        "172.18.",
        "172.19.",
        "172.20.",
        "172.21.",
        "172.22.",
        "172.23.",
        "172.24.",
        "172.25.",
        "172.26.",
        "172.27.",
        "172.28.",
        "172.29.",
        "172.30.",
        "172.31.",
        "169.254.",
        "[::1]",
        "0.0.0.0",
    ]

    for pattern in private_patterns:
        if hostname.startswith(pattern) or hostname == pattern.rstrip("."):
            return True

    # Block non-http schemes
    return parsed.scheme not in ("http", "https")
