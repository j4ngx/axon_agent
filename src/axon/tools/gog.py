"""GOG (Google Workspace) tool implementation.

This module provides tools that wrap the ``gog`` CLI to interact with:
- Gmail (search, send, read)
- Google Calendar (list, create, update)
- Google Drive (search)
- Google Sheets (get, update, append)
- Google Docs (cat, export)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from axon.tools.base import Tool

logger = logging.getLogger(__name__)


class GogTool(Tool):
    """Base class for GOG-related tools to share common CLI execution logic."""

    async def _run_gog(self, args: list[str]) -> str:
        """Execute a ``gog`` command and return stdout or stderr."""
        # Use GOG_ACCOUNT from environment if available
        account = os.getenv("GOG_ACCOUNT")
        cmd_args = ["gog"]
        if account:
            cmd_args.extend(["--account", account])
        cmd_args.extend(args)

        logger.debug("Executing gog command", extra={"args": cmd_args})

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error("Gog command failed", extra={"error": error_msg, "code": process.returncode})
                return f"Error: {error_msg}"

            return stdout.decode().strip()
        except Exception as e:
            logger.exception("Failed to execute gog command")
            return f"Error: Unexpected failure: {e}"


class GogGmailTool(GogTool):
    """Tool for Gmail operations."""

    @property
    def name(self) -> str:
        return "gog_gmail"

    @property
    def description(self) -> str:
        return (
            "Search or send emails via Gmail. "
            "Commands: 'search <query>', 'send --to <to> --subject <subj> --body <body>'. "
            "Example: search 'newer_than:1d'"
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command type: 'search' or 'send'"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "Arguments for the command"},
            },
            "required": ["command", "args"],
        }

    async def run(self, command: str, args: list[str]) -> str:
        if command not in ["search", "send"]:
            return f"Error: Unsupported Gmail command '{command}'"
        return await self._run_gog(["gmail", command] + args)


class GogCalendarTool(GogTool):
    """Tool for Google Calendar operations."""

    @property
    def name(self) -> str:
        return "gog_calendar"

    @property
    def description(self) -> str:
        return (
            "Manage Google Calendar events. "
            "Commands: 'events <id>', 'create <id> --summary <s> --from <f> --to <t>'. "
            "Use 'primary' as the calendar ID for the main account."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command type: 'events', 'create', 'update'"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "Arguments for the command"},
            },
            "required": ["command", "args"],
        }

    async def run(self, command: str, args: list[str]) -> str:
        if command not in ["events", "create", "update", "colors"]:
            return f"Error: Unsupported Calendar command '{command}'"
        return await self._run_gog(["calendar", command] + args)


class GogSheetsTool(GogTool):
    """Tool for Google Sheets operations."""

    @property
    def name(self) -> str:
        return "gog_sheets"

    @property
    def description(self) -> str:
        return (
            "Interact with Google Sheets. "
            "Commands: 'get <id> <range>', 'append <id> <range> --values-json <json>'. "
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command type: 'get', 'append', 'update', 'clear'"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "Arguments for the command"},
            },
            "required": ["command", "args"],
        }

    async def run(self, command: str, args: list[str]) -> str:
        if command not in ["get", "append", "update", "clear", "metadata"]:
            return f"Error: Unsupported Sheets command '{command}'"
        return await self._run_gog(["sheets", command] + args)
