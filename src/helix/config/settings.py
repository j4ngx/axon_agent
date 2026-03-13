"""Centralised application settings.

Configuration is split into two sources:

- **``config.yml``** — non-secret, version-controlled application settings
  (models, timeouts, agent behaviour, skill declarations, …).
- **``.env``** — secrets only (API keys, bot tokens).

At startup both are loaded, merged into a single validated ``Settings``
object, and injected into every component via the DI container.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = src/helix/config/../../..
_SOURCE_ROOT: Path = Path(__file__).resolve().parents[3]


def _find_project_root() -> Path:
    """Locate the project root directory.

    When installed as a package (e.g. inside ``.venv``), the source-relative
    path won't contain ``config.yml``.  Fall back to the current working
    directory which is ``/app/`` in the Docker container.
    """
    if (_SOURCE_ROOT / "config.yml").exists():
        return _SOURCE_ROOT
    return Path.cwd()


_PROJECT_ROOT: Path = _find_project_root()
_ENV_FILE: Path = _PROJECT_ROOT / ".env"
_DEFAULT_CONFIG_YML: Path = _PROJECT_ROOT / "config.yml"

# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------


def load_yaml_config(path: str | Path = "config.yml") -> dict[str, Any]:
    """Read and parse a YAML configuration file.

    Args:
        path: Filesystem path to the YAML file.

    Returns:
        A nested dict of configuration values.  Returns an empty dict
        if the file does not exist.
    """
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# ---------------------------------------------------------------------------
# Nested config models (plain Pydantic — not BaseSettings)
# ---------------------------------------------------------------------------


class GroqConfig(BaseModel):
    """Groq provider settings (non-secret)."""

    model: str = "llama-3.3-70b-versatile"
    timeout: float = 30.0


class OpenRouterConfig(BaseModel):
    """OpenRouter provider settings (non-secret)."""

    model: str = "meta-llama/llama-3.3-70b-instruct:free"
    timeout: float = 60.0
    base_url: str = "https://openrouter.ai/api/v1"


class LLMConfig(BaseModel):
    """Top-level LLM configuration."""

    groq: GroqConfig = Field(default_factory=GroqConfig)
    openrouter: OpenRouterConfig = Field(default_factory=OpenRouterConfig)
    primary: str = "groq"
    fallback: str = "openrouter"


class AgentConfig(BaseModel):
    """Agent loop configuration."""

    max_iterations: int = 5
    history_limit: int = 20
    system_prompt_path: str = "prompts/system_prompt.md"

    def load_system_prompt(self) -> str:
        """Read the system prompt from the referenced Markdown file.

        Returns:
            The raw content of the Markdown file.  Falls back to a
            minimal built-in prompt if the file cannot be found.
        """
        path = Path(self.system_prompt_path)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return "You are Helix, a helpful personal AI assistant. Be concise and accurate."


class MemoryConfig(BaseModel):
    """Persistence configuration."""

    project_id: str | None = None


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"


class TelegramConfig(BaseModel):
    """Telegram-specific configuration (non-secret parts)."""

    allowed_user_ids: list[int] = Field(default_factory=list)


class WeatherConfig(BaseModel):
    """Weather configuration for daily briefing."""

    latitude: float = 37.1773
    longitude: float = -3.5986
    location_name: str = "Granada"


class VisionConfig(BaseModel):
    """Vision model configuration."""

    model: str = "meta-llama/llama-4-scout-17b-16e-instruct"


class DocumentConfig(BaseModel):
    """Document processing configuration."""

    chunk_size: int = 800
    chunk_overlap: int = 100


class TTSConfig(BaseModel):
    """ElevenLabs text-to-speech configuration."""

    voice_id: str = "Ir1QNHvhaJXbAGhT50w3"
    model_id: str = "eleven_multilingual_v2"
    output_format: str = "mp3_44100_128"


class SkillConfig(BaseModel):
    """Declaration of a single skill (builtin or MCP).

    Attributes:
        name: Human-readable skill identifier.
        type: ``"builtin"`` or ``"mcp"``.
        enabled: Whether to load this skill at startup.
        transport: MCP transport type (``"stdio"`` currently supported).
        command: Executable to launch (MCP stdio).
        args: Command-line arguments for the MCP process.
        env: Extra environment variables for the MCP process.
        url: URL for future HTTP-based MCP transport.
    """

    name: str
    type: str = "builtin"
    enabled: bool = True

    # MCP-specific fields (ignored for builtin)
    transport: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None


# ---------------------------------------------------------------------------
# Root Settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Root settings — merges ``.env`` secrets with ``config.yml`` values.

    Secrets are loaded from environment variables / ``.env``.
    Everything else comes from ``config.yml`` (injected via the
    ``from_yaml`` class method).
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Secrets (from .env) ---------------------------------------------------
    telegram_bot_token: str
    telegram_allowed_user_ids: list[int] = Field(default_factory=list)
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    elevenlabs_api_key: str = ""
    google_application_credentials: str = "./service-account.json"

    # -- YAML-sourced config (non-secret) --------------------------------------
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    skills: list[SkillConfig] = Field(default_factory=list)
    weather: WeatherConfig = Field(default_factory=WeatherConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    document: DocumentConfig = Field(default_factory=DocumentConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)

    # -- Validators ------------------------------------------------------------

    @field_validator("telegram_allowed_user_ids", mode="before")
    @classmethod
    def parse_allowed_user_ids(cls, value: str | int | list[int]) -> list[int]:
        """Accept a comma-separated string, a single int, or an already-parsed list."""
        if isinstance(value, str):
            return [int(uid.strip()) for uid in value.split(",") if uid.strip()]
        if isinstance(value, int):
            return [value]
        return value

    @field_validator("google_application_credentials", mode="after")
    @classmethod
    def resolve_credentials_path(cls, v: str) -> str:
        """Resolve relative credential paths against the project root."""
        path = Path(v)
        if not path.is_absolute():
            return str(_PROJECT_ROOT / v)
        return v

    # -- Factory ---------------------------------------------------------------

    @classmethod
    def from_yaml(
        cls,
        yaml_path: str | Path | None = None,
        **overrides: Any,
    ) -> Settings:
        """Build a ``Settings`` by layering YAML config on top of env secrets.

        Args:
            yaml_path: Path to the YAML configuration file.
            **overrides: Explicit keyword overrides (highest priority).

        Returns:
            A fully-validated ``Settings``.
        """
        yaml_data = load_yaml_config(yaml_path if yaml_path is not None else _DEFAULT_CONFIG_YML)

        init_kwargs: dict[str, Any] = {}

        if "telegram" in yaml_data:
            tg_data = yaml_data["telegram"]
            init_kwargs["telegram"] = TelegramConfig(**tg_data)
            # Seed the flat env-alias from YAML so config.yml alone is sufficient;
            # TELEGRAM_ALLOWED_USER_IDS in .env takes priority (overrides via env source).
            if tg_data.get("allowed_user_ids"):
                init_kwargs.setdefault("telegram_allowed_user_ids", tg_data["allowed_user_ids"])
        if "llm" in yaml_data:
            init_kwargs["llm"] = LLMConfig(**yaml_data["llm"])
        if "agent" in yaml_data:
            init_kwargs["agent"] = AgentConfig(**yaml_data["agent"])
        if "memory" in yaml_data:
            init_kwargs["memory"] = MemoryConfig(**yaml_data["memory"])
        if "logging" in yaml_data:
            init_kwargs["logging"] = LoggingConfig(**yaml_data["logging"])
        if "skills" in yaml_data:
            init_kwargs["skills"] = [SkillConfig(**s) for s in yaml_data["skills"]]
        if "weather" in yaml_data:
            init_kwargs["weather"] = WeatherConfig(**yaml_data["weather"])
        if "vision" in yaml_data:
            init_kwargs["vision"] = VisionConfig(**yaml_data["vision"])
        if "document" in yaml_data:
            init_kwargs["document"] = DocumentConfig(**yaml_data["document"])
        if "tts" in yaml_data:
            init_kwargs["tts"] = TTSConfig(**yaml_data["tts"])

        init_kwargs.update(overrides)
        return cls(**init_kwargs)  # type: ignore[arg-type]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (YAML + env merged)."""
    return Settings.from_yaml()
