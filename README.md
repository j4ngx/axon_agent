# Helix

A personal, local-first AI agent with Telegram interface, LLM reasoning, tool execution, and persistent memory.

## Features

- **Telegram interface** — interact via long-polling with aiogram v3
- **Multi-LLM** — Groq (primary) + OpenRouter (fallback), automatic failover
- **Tool system** — extensible via built-in tools, skills, or MCP servers
- **Persistent memory** — Firestore conversation history per user
- **Reminders & scheduler** — schedule one-time and recurring reminders via natural language; background scheduler delivers them through Telegram
- **Google Workspace** — Gmail, Calendar, and Sheets via `gog` CLI
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
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Firebase service-account JSON | Yes |

### Application Settings (`config.yml`)

All non-secret settings live in `config.yml`:

- **LLM providers** — models, timeouts, primary/fallback selection
- **Agent** — max iterations, history window, system prompt path
- **Memory** — Firestore project ID for persistent storage
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
├── firebase.json              # Firebase project configuration
├── firestore.rules            # Firestore security rules
├── firestore.indexes.json     # Firestore composite index definitions
├── service-account.json       # Firebase service account key (gitignored)
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
│   │   ├── models.py          # Data models (Message, Reminder)
│   │   ├── db.py              # Firebase initialisation
│   │   ├── repositories.py    # Chat history repository
│   │   └── reminder_repository.py # Reminder CRUD (Firestore)
│   ├── scheduler/
│   │   └── service.py         # Background reminder scheduler
│   ├── tools/
│   │   ├── base.py            # Tool ABC
│   │   ├── registry.py        # Name-indexed catalogue
│   │   ├── get_current_time.py
│   │   ├── gog.py             # Google Workspace (Gmail/Calendar/Sheets)
│   │   └── reminder.py        # Reminder management tool
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

## Firebase Setup

Helix uses Cloud Firestore for persistent storage. The Firebase project is
configured in `firebase.json`.

### Prerequisites

- A Firebase project (e.g., `axon-429c0`)
- A service account key (`service-account.json`)
- Firebase CLI (`npm install -g firebase-tools`)

### Deploy Firestore Rules & Indexes

```bash
# Login (first time)
firebase login

# Set project
firebase use axon-429c0

# Deploy everything
firebase deploy --only firestore

# Or deploy individually
firebase deploy --only firestore:rules
firebase deploy --only firestore:indexes
```

### Files

| File | Purpose |
|---|---|
| `firebase.json` | Firebase project config (database, rules path, indexes path) |
| `firestore.rules` | Security rules — deny-all for clients (Admin SDK bypasses) |
| `firestore.indexes.json` | Composite indexes needed for collection group queries |
| `service-account.json` | Service account key (not committed to git) |

## Adding Tools

### Built-in Tool

1. Create a class in `src/helix/tools/` that extends `Tool` ABC
2. Register it in `src/helix/skills/loader.py` → `_discover_builtins()`
3. Add an entry to `config.yml` under `skills`

> **Note:** Tools that require DI dependencies (like `ReminderTool`) are
> registered directly in `container.py` instead of via the skill loader.

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
uv run python -m pytest tests/

# Run tests with coverage
uv run python -m pytest tests/ --cov=src/helix --cov-report=html

# Format
uv run ruff format

# Lint (with auto-fix)
uv run ruff check --fix

# Deploy Firestore config
firebase deploy --only firestore

# Run the bot
uv run helix
```

## Architecture

```
Telegram → Handlers → AgentLoop → LLM (Groq/OpenRouter)
                         ↕              ↕
                      Memory         Tools/Skills
                   (Firestore)       (Registry)
                         ↑
               SchedulerService ──→ Telegram (notifications)
```

The DI `Container` wires everything at startup. The `AgentLoop` implements a
think-act-observe cycle: it calls the LLM, executes any requested tools,
feeds results back, and repeats until it gets a final text answer or hits
the iteration limit.

The `SchedulerService` runs as a background `asyncio.Task` alongside the
Telegram polling loop. Every 30 seconds it queries Firestore for due
reminders and delivers them as Telegram messages.

## Firestore Data Model

All persistent data is stored in Cloud Firestore (project `axon-429c0`).

```
(default) database
└── users/{user_id}
    ├── messages/{message_id}     # Chat history
    │   ├── role: string
    │   ├── content: string
    │   └── timestamp: timestamp
    └── reminders/{reminder_id}   # Scheduled reminders
        ├── user_id: number
        ├── message: string
        ├── trigger_at: timestamp
        ├── recurrence: string | null   (daily | weekdays | weekly | monthly)
        ├── status: string              (pending | completed | cancelled)
        └── created_at: timestamp
```

### Composite Indexes

| Collection Group | Fields | Purpose |
|---|---|---|
| `reminders` | `status` ASC, `trigger_at` ASC | `get_due_reminders()` — scheduler scans all users |

Indexes are defined in `firestore.indexes.json` and deployed with `firebase deploy --only firestore:indexes`.

### Security Rules

Firestore rules deny all client-side access (`allow read, write: if false`).
Helix uses the Firebase Admin SDK, which bypasses security rules entirely.
This means no public or browser client can read or write data.

## Reminders

Helix supports scheduled reminders that the user can create, list, and cancel
through natural language in Telegram.

### How It Works

1. **User** asks Helix to remind them of something (e.g., _"recuérdame mañana a las 9 ir al médico"_)
2. **LLM** calls the `reminder` tool with `command: "create"`, `message`, `trigger_at` (ISO-8601 UTC), and optional `recurrence`
3. **ReminderTool** validates the input and persists a `Reminder` document in `users/{user_id}/reminders/`
4. **SchedulerService** (background loop every 30 s) queries all pending reminders with `trigger_at <= now`
5. When a reminder is due, the scheduler sends a Telegram message `🔔 Reminder: <message>` and either:
   - **One-time**: marks it `completed`
   - **Recurring**: computes `next_trigger` and updates `trigger_at`

### Supported Commands

| Command | Description | Required Params |
|---|---|---|
| `create` | Schedule a new reminder | `message`, `trigger_at` |
| `list` | Show all pending reminders | — |
| `cancel` | Cancel a reminder by ID | `reminder_id` |

### Recurrence Patterns

| Pattern | Behaviour |
|---|---|
| _(none)_ | One-time — fires once, then completed |
| `daily` | Every day at the same time |
| `weekdays` | Monday–Friday, skips weekends |
| `weekly` | Same day every week |
| `monthly` | Same day each month (capped at 28th) |

### Example Interactions

```
User:  Recuérdame comprar leche mañana a las 10
Helix: Reminder created (ID: abc123). Scheduled for 2026-03-12T10:00:00+00:00.

User:  Lista mis recordatorios
Helix: Pending reminders (1):
       - abc123: Comprar leche — 2026-03-12T10:00:00+00:00

User:  Cancela el recordatorio abc123
Helix: Reminder abc123 has been cancelled.
```

## License

MIT
