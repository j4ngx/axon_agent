"""Tests for the skill loader."""

from __future__ import annotations

import pytest

from helix.config.settings import SkillConfig
from helix.skills.loader import _BUILTIN_GROUPS, _BUILTIN_SKILLS, _discover_builtins, load_skills
from helix.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def _reset_builtins() -> None:
    """Ensure builtin discovery runs fresh for each test."""
    _BUILTIN_SKILLS.clear()
    _BUILTIN_GROUPS.clear()


class TestLoadBuiltinGroupSkill:
    """Loading a group skill (e.g. ``gog``) registers all member tools."""

    @pytest.mark.asyncio
    async def test_when_loading_gog_group_expect_all_tools_registered(self) -> None:
        # Arrange
        registry = ToolRegistry()
        configs = [SkillConfig(name="gog", type="builtin", enabled=True)]

        # Act
        await load_skills(registry, configs)

        # Assert
        assert registry.get("gog_gmail") is not None
        assert registry.get("gog_calendar") is not None
        assert registry.get("gog_sheets") is not None

    @pytest.mark.asyncio
    async def test_when_loading_gog_group_expect_three_tools_total(self) -> None:
        registry = ToolRegistry()
        configs = [SkillConfig(name="gog", type="builtin", enabled=True)]

        await load_skills(registry, configs)

        assert len(registry.list_tools()) == 3


class TestLoadBuiltinDirectSkill:
    """Loading a direct skill name registers exactly that tool."""

    @pytest.mark.asyncio
    async def test_when_loading_get_current_time_expect_registered(self) -> None:
        registry = ToolRegistry()
        configs = [SkillConfig(name="get_current_time", type="builtin", enabled=True)]

        await load_skills(registry, configs)

        assert registry.get("get_current_time") is not None
        assert len(registry.list_tools()) == 1


class TestLoadSkillsEdgeCases:
    """Edge cases: unknown names, disabled skills, mixed configs."""

    @pytest.mark.asyncio
    async def test_when_loading_unknown_skill_expect_no_tools(self) -> None:
        registry = ToolRegistry()
        configs = [SkillConfig(name="nonexistent", type="builtin", enabled=True)]

        await load_skills(registry, configs)

        assert len(registry.list_tools()) == 0

    @pytest.mark.asyncio
    async def test_when_skill_disabled_expect_not_loaded(self) -> None:
        registry = ToolRegistry()
        configs = [SkillConfig(name="gog", type="builtin", enabled=False)]

        await load_skills(registry, configs)

        assert len(registry.list_tools()) == 0

    @pytest.mark.asyncio
    async def test_when_loading_group_and_direct_expect_all_registered(self) -> None:
        registry = ToolRegistry()
        configs = [
            SkillConfig(name="get_current_time", type="builtin", enabled=True),
            SkillConfig(name="gog", type="builtin", enabled=True),
        ]

        await load_skills(registry, configs)

        assert registry.get("get_current_time") is not None
        assert registry.get("gog_gmail") is not None
        assert registry.get("gog_calendar") is not None
        assert registry.get("gog_sheets") is not None
        assert len(registry.list_tools()) == 4


class TestDiscoverBuiltins:
    """Verify _discover_builtins populates both dicts correctly."""

    def test_when_discover_called_expect_groups_populated(self) -> None:
        _discover_builtins()

        assert "gog" in _BUILTIN_GROUPS
        assert set(_BUILTIN_GROUPS["gog"]) == {"gog_gmail", "gog_calendar", "gog_sheets"}

    def test_when_discover_called_expect_individual_skills_populated(self) -> None:
        _discover_builtins()

        assert "get_current_time" in _BUILTIN_SKILLS
        assert "gog_gmail" in _BUILTIN_SKILLS
        assert "gog_calendar" in _BUILTIN_SKILLS
        assert "gog_sheets" in _BUILTIN_SKILLS
