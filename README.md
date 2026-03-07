# Helix

A personal, local-first AI agent with Telegram interface, LLM reasoning, tool execution, and persistent memory.

## Features

- **Telegram interface** — interact via long-polling with aiogram v3
- **Multi-LLM** — Groq (primary) + OpenRouter (fallback), automatic failover
- **Tool system** — extensible via built-in tools, skills, or MCP servers
- **Persistent memory** — SQLite conversation history per user via SQLAlchemy async
- **YAML config** — non-secret settings in `config.yml`, secrets in `.env`
- **Dependency injection** — clean, hand-rolled DI container
- **Structured logging** — JSON output with automatic secret redaction

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## Quick Start

```bash
# Clone and enter
git clone <repo-url> helix_agent && cd helix_agent

# Install dependencies
uv sync

# Configure
cp .env.example .env
cp config.example.yml config.yml
# Edit .env with your API keys and bot token
# Edit config.yml to customise models, agent behaviour, skills

# Run
uv run helix
```

## Configuration

### Secrets (`.env`)

| Variable | Description | Required |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated Telegram user IDs | Yes |
| `GROQ_API_KEY` | Groq API key | Yes |
| `OPENROUTER_API_KEY` | OpenRouter API key | No |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account (future) | No |

### Application Settings (`config.yml`)

All non-secret settings live in `config.yml`:

- **LLM providers** — models, timeouts, primary/fallback selection
- **Agent** — max iterations, history window, system prompt path
- **Memory** — SQLite database path
- **Logging** — log level
- **Skills** — built-in tools and MCP server connections

See [config.example.yml](config.example.yml) for the full reference.

### System Prompt

The agent's system prompt is a standalone Markdown file at `prompts/system_prompt.md`.
Edit it to change Helix's personality, response style, or safety guidelines.
Placeholders `{current_time}` and `{tools_description}` are injected at runtime.

## Project Structure

```
helix_agent/
├── config.yml                 # Application settings (non-secret)
├── .env                       # Secrets (API keys, tokens)
├── prompts/
│   └── system_prompt.md       # Agent system prompt (Markdown)
├── src/helix/
│   ├── main.py                # Entry point
│   ├── config/
│   │   └── settings.py        # Pydantic settings (YAML + .env merge)
│   ├── di/
│   │   └── container.py       # Dependency injection container
│   ├── agent/
│   │   ├── context.py         # Per-invocation state
│   │   └── loop.py            # Core reasoning loop
│   ├── llm/
│   │   ├── base.py            # Protocol + DTOs
│   │   ├── groq_client.py     # Groq SDK client
│   │   ├── openrouter_client.py # OpenRouter httpx client
│   │   └── fallback.py        # Primary/fallback wrapper
│   ├── memory/
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── db.py              # Engine + session factory
│   │   └── repositories.py   # Data access layer
│   ├── tools/
│   │   ├── base.py            # Tool ABC
│   │   ├── registry.py        # Name-indexed catalogue
│   │   └── get_current_time.py
│   ├── skills/
│   │   ├── loader.py          # Skill loader (builtin + MCP)
│   │   └── mcp_adapter.py     # MCP-to-Tool adapter
│   ├── telegram/
│   │   ├── bot.py             # Bot + dispatcher setup
│   │   └── handlers.py        # Auth middleware + message routing
│   ├── logging/
│   │   └── setup.py           # JSON logging + secret redaction
│   └── exceptions.py          # Domain exception hierarchy
├── tests/
│   └── unit/                  # Unit tests (pytest + pytest-asyncio)
└── pyproject.toml             # Project metadata, deps, tool config
```

## Adding Tools

### Built-in Tool

1. Create a class in `src/helix/tools/` that extends `Tool` ABC
2. Register it in `src/helix/skills/loader.py` → `_discover_builtins()`
3. Add an entry to `config.yml` under `skills`

### MCP Server

1. Install the MCP extra: `uv sync --extra mcp`
2. Add an entry to `config.yml`:

```yaml
skills:
  - name: "web_search"
    type: "mcp"
    enabled: true
    transport: "stdio"
    command: "npx"
    args: ["-y", "@anthropic/mcp-server-web-search"]
    env:
      BRAVE_API_KEY: "${BRAVE_API_KEY}"
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/helix --cov-report=html

# Format
uv run ruff format

# Lint (with auto-fix)
uv run ruff check --fix

# Run the bot
uv run helix
```

## Architecture

```
Telegram → Handlers → AgentLoop → LLM (Groq/OpenRouter)
                         ↕              ↕
                      Memory         Tools/Skills
                     (SQLite)        (Registry)
```

The DI `Container` wires everything at startup. The `AgentLoop` implements a
think-act-observe cycle: it calls the LLM, executes any requested tools,
feeds results back, and repeats until it gets a final text answer or hits
the iteration limit.

## License

MIT
