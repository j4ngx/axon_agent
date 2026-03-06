"""Unit tests for GOG tools."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from axon.tools.gog import GogGmailTool, GogCalendarTool, GogSheetsTool


@pytest.fixture
def mock_subprocess():
    with patch("asyncio.create_subprocess_exec") as mock:
        process = AsyncMock()
        process.returncode = 0
        process.communicate.return_value = (b"mock output", b"")
        mock.return_value = process
        yield mock


class TestGogTools:
    """Tests for GOG tool wrappers."""

    @pytest.mark.asyncio
    async def test_gmail_search_command(self, mock_subprocess):
        tool = GogGmailTool()
        result = await tool.run(command="search", args=["newer_than:1d"])

        assert result == "mock output"
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0]
        assert "gmail" in args
        assert "search" in args
        assert "newer_than:1d" in args

    @pytest.mark.asyncio
    async def test_calendar_events_command(self, mock_subprocess):
        tool = GogCalendarTool()
        result = await tool.run(command="events", args=["primary"])

        assert result == "mock output"
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0]
        assert "calendar" in args
        assert "events" in args
        assert "primary" in args

    @pytest.mark.asyncio
    async def test_sheets_get_command(self, mock_subprocess):
        tool = GogSheetsTool()
        result = await tool.run(command="get", args=["sheet123", "A1:B10"])

        assert result == "mock output"
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0]
        assert "sheets" in args
        assert "get" in args
        assert "sheet123" in args

    @pytest.mark.asyncio
    async def test_command_failure(self, mock_subprocess):
        # Setup failure
        process = mock_subprocess.return_value
        process.returncode = 1
        process.communicate.return_value = (b"", b"permission denied")

        tool = GogGmailTool()
        result = await tool.run(command="search", args=["query"])

        assert "Error: permission denied" in result
