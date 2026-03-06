"""Tests for the ``Settings`` configuration model."""

from __future__ import annotations

from pathlib import Path

from axon.config.settings import (
    AgentConfig,
    GroqConfig,
    LLMConfig,
    LoggingConfig,
    MemoryConfig,
    OpenRouterConfig,
    Settings,
    SkillConfig,
    TelegramConfig,
    load_yaml_config,
)


class TestLoadYamlConfig:
    """Tests for ``load_yaml_config``."""

    def test_when_file_missing_expect_empty_dict(self, tmp_path: Path) -> None:
        result = load_yaml_config(tmp_path / "nope.yml")
        assert result == {}

    def test_when_valid_yaml_expect_parsed_dict(self, tmp_path: Path) -> None:
        yml = tmp_path / "test.yml"
        yml.write_text("agent:\n  max_iterations: 10\n")
        result = load_yaml_config(yml)
        assert result["agent"]["max_iterations"] == 10


class TestNestedConfigs:
    """Tests for nested Pydantic config models."""

    def test_when_default_groq_config_expect_defaults(self) -> None:
        cfg = GroqConfig()
        assert cfg.model == "llama-3.3-70b-versatile"
        assert cfg.timeout == 30.0

    def test_when_default_openrouter_config_expect_defaults(self) -> None:
        cfg = OpenRouterConfig()
        assert "openrouter.ai" in cfg.base_url

    def test_when_default_llm_config_expect_groq_primary(self) -> None:
        cfg = LLMConfig()
        assert cfg.primary == "groq"
        assert cfg.fallback == "openrouter"

    def test_when_default_logging_config_expect_info(self) -> None:
        assert LoggingConfig().level == "INFO"

    def test_when_telegram_config_expect_empty_user_ids(self) -> None:
        assert TelegramConfig().allowed_user_ids == []


class TestAgentConfig:
    """Tests for ``AgentConfig``."""

    def test_when_default_expect_system_prompt_path(self) -> None:
        cfg = AgentConfig()
        assert cfg.system_prompt_path == "prompts/system_prompt.md"

    def test_when_loading_prompt_from_file_expect_file_contents(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("# Custom Prompt\nHello!")
        cfg = AgentConfig(system_prompt_path=str(prompt_file))
        result = cfg.load_system_prompt()
        assert result == "# Custom Prompt\nHello!"

    def test_when_prompt_file_missing_expect_fallback(self) -> None:
        cfg = AgentConfig(system_prompt_path="/nonexistent/prompt.md")
        result = cfg.load_system_prompt()
        assert "Axon" in result
        assert len(result) > 10


class TestMemoryConfig:
    """Tests for ``MemoryConfig``."""

    def test_when_memory_path_expect_resolved_absolute(self) -> None:
        cfg = MemoryConfig(db_path="./test.db")
        assert Path(cfg.db_path).is_absolute()

    def test_when_in_memory_path_expect_unchanged(self) -> None:
        cfg = MemoryConfig(db_path=":memory:")
        assert cfg.db_path == ":memory:"


class TestSkillConfig:
    """Tests for ``SkillConfig``."""

    def test_when_builtin_skill_expect_defaults(self) -> None:
        skill = SkillConfig(name="test")
        assert skill.type == "builtin"
        assert skill.enabled is True
        assert skill.transport is None

    def test_when_mcp_skill_expect_fields_populated(self) -> None:
        skill = SkillConfig(
            name="web",
            type="mcp",
            transport="stdio",
            command="npx",
            args=["-y", "server"],
        )
        assert skill.type == "mcp"
        assert skill.command == "npx"
        assert len(skill.args) == 2


class TestSettings:
    """Tests for the root ``Settings`` model."""

    def test_when_valid_env_expect_settings_created(self) -> None:
        s = Settings(
            telegram_bot_token="test:token",
            telegram_allowed_user_ids="123,456",
            groq_api_key="key",
        )
        assert s.telegram_allowed_user_ids == [123, 456]

    def test_when_allowed_user_ids_list_expect_passthrough(self) -> None:
        s = Settings(
            telegram_bot_token="test:token",
            telegram_allowed_user_ids=[1, 2, 3],
        )
        assert s.telegram_allowed_user_ids == [1, 2, 3]

    def test_when_from_yaml_expect_merged_config(self, tmp_path: Path) -> None:
        yml = tmp_path / "config.yml"
        yml.write_text("agent:\n  max_iterations: 99\nlogging:\n  level: DEBUG\n")
        s = Settings.from_yaml(
            yaml_path=yml,
            telegram_bot_token="test:token",
        )
        assert s.agent.max_iterations == 99
        assert s.logging.level == "DEBUG"
