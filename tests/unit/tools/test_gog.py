"""Unit tests for GOG tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from helix.tools.gog import GogCalendarTool, GogGmailTool, GogSheetsTool


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

    @pytest.mark.asyncio
    async def test_unsupported_gmail_command(self, mock_subprocess):
        """Unsupported commands should return an error without calling gog."""
        tool = GogGmailTool()
        result = await tool.run(command="delete", args=[])

        assert "Error: Unsupported Gmail command 'delete'" in result
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsupported_calendar_command(self, mock_subprocess):
        tool = GogCalendarTool()
        result = await tool.run(command="remove", args=[])

        assert "Error: Unsupported Calendar command 'remove'" in result
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsupported_sheets_command(self, mock_subprocess):
        tool = GogSheetsTool()
        result = await tool.run(command="drop", args=[])

        assert "Error: Unsupported Sheets command 'drop'" in result
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_gog_account_env_injection(self, mock_subprocess):
        """When GOG_ACCOUNT is set, --account should appear in args."""
        with patch.dict("os.environ", {"GOG_ACCOUNT": "test@gmail.com"}):
            tool = GogGmailTool()
            await tool.run(command="search", args=["query"])

        args = mock_subprocess.call_args[0]
        assert "--account" in args
        assert "test@gmail.com" in args

    @pytest.mark.asyncio
    async def test_gog_account_not_set(self, mock_subprocess):
        """When GOG_ACCOUNT is not set, --account should NOT appear."""
        with patch.dict("os.environ", {}, clear=True):
            tool = GogGmailTool()
            await tool.run(command="search", args=["query"])

        args = mock_subprocess.call_args[0]
        assert "--account" not in args

    @pytest.mark.asyncio
    async def test_subprocess_timeout(self):
        """A hung subprocess should be killed and return a timeout error."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            process = AsyncMock()
            # Simulate a process that never completes
            process.communicate.side_effect = TimeoutError()
            process.kill = AsyncMock()
            mock_exec.return_value = process

            tool = GogGmailTool()
            result = await tool.run(command="search", args=["query"])

            assert "timed out" in result.lower()
