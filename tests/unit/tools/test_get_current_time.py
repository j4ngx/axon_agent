"""Tests for the ``GetCurrentTimeTool`` builtin tool."""

from __future__ import annotations

from freezegun import freeze_time

from helix.tools.get_current_time import GetCurrentTimeTool


class TestGetCurrentTimeTool:
    """Unit tests for ``GetCurrentTimeTool``."""

    def setup_method(self) -> None:
        """Create a fresh tool instance for each test."""
        self.tool = GetCurrentTimeTool()

    def test_when_checking_name_expect_get_current_time(self) -> None:
        assert self.tool.name == "get_current_time"

    def test_when_checking_description_expect_non_empty_string(self) -> None:
        assert isinstance(self.tool.description, str)
        assert len(self.tool.description) > 0

    def test_when_checking_parameters_schema_expect_empty_object(self) -> None:
        schema = self.tool.parameters_schema
        assert schema["type"] == "object"
        assert schema["properties"] == {}

    @freeze_time("2026-03-06 14:30:00", tz_offset=0)
    async def test_when_run_expect_iso_format_in_output(self) -> None:
        result = await self.tool.run()
        assert "2026-03-06" in result

    @freeze_time("2026-03-06 14:30:00", tz_offset=0)
    async def test_when_run_expect_human_readable_format_in_output(self) -> None:
        result = await self.tool.run()
        assert "Friday" in result
        assert "March" in result

    def test_when_serialising_expect_valid_openai_schema(self) -> None:
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "get_current_time"
        assert "parameters" in schema["function"]
