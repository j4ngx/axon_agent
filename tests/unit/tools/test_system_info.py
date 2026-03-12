"""Tests for the ``SystemInfoTool`` builtin tool."""

from __future__ import annotations

from helix.tools.system_info import SystemInfoTool


class TestSystemInfoTool:
    """Unit tests for ``SystemInfoTool``."""

    def setup_method(self) -> None:
        self.tool = SystemInfoTool()

    def test_when_checking_name_expect_system_info(self) -> None:
        assert self.tool.name == "system_info"

    def test_when_checking_description_expect_non_empty_string(self) -> None:
        assert isinstance(self.tool.description, str)
        assert len(self.tool.description) > 0

    def test_when_checking_parameters_schema_expect_empty_object(self) -> None:
        schema = self.tool.parameters_schema
        assert schema["type"] == "object"
        assert schema["properties"] == {}

    def test_when_serialising_expect_valid_openai_schema(self) -> None:
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "system_info"

    async def test_when_run_expect_os_info_in_output(self) -> None:
        result = await self.tool.run()
        assert "OS:" in result
        assert "Hostname:" in result

    async def test_when_run_expect_cpu_info_in_output(self) -> None:
        result = await self.tool.run()
        assert "CPU cores:" in result

    async def test_when_run_expect_disk_info_in_output(self) -> None:
        result = await self.tool.run()
        assert "Disk" in result
        assert "GB" in result

    async def test_when_run_expect_load_average_in_output(self) -> None:
        result = await self.tool.run()
        assert "Load avg" in result
