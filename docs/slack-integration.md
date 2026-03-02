# Slack Integration Design

> **Status:** Implemented — `bots/slackbot/` is live.
> Run `uv sync && uv run slackbot` after adding tokens to `.env`.

## Goal

Allow team members to interact with DevBots from Slack — run bot analyses, receive reports, and get proactive notifications — without leaving their messaging tool.

## Design Principles

- **Orchestrator-first**: Slack is a transport channel; all routing and intent parsing goes through existing orchestrator logic (`bot_invoker.py`, `registry.py`).
- **No duplication**: The Slack bot reuses the orchestrator's Claude-based intent parser and `invoke_bot()` directly — it does not re-implement any bot logic.
- **Stateless per message**: Each Slack message is handled independently (no persistent chat session), similar to how the dashboard triggers single-shot report generation.
- **Progressive rollout**: Start with Socket Mode (no public URL) for internal use, move to HTTP/webhook mode for production if needed.

---

## Architecture

```
Slack user
    │
    │  @devbot analyze myproject   (DM or channel mention)
    ▼
┌─────────────────────────────────────────────────────┐
│  bots/slackbot/                                      │
│  ┌────────────┐   ┌─────────────┐   ┌────────────┐ │
│  │  app.py    │──▶│  handler.py │──▶│ formatter  │ │
│  │  Bolt app  │   │  Intent →   │   │  BotResult │ │
│  │  Socket /  │   │  invoke_bot │   │  → Slack   │ │
│  │  HTTP mode │   └──────┬──────┘   └────────────┘ │
│  └────────────┘          │                          │
└─────────────────────────-│──────────────────────────┘
                           │ reuses
                           ▼
┌──────────────────────────────────────────────────────┐
│  orchestrator/                                        │
│  ┌─────────────────┐   ┌──────────────────────────┐ │
│  │  bot_invoker.py │   │  registry.py             │ │
│  │  invoke_bot()   │   │  ProjectRegistry          │ │
│  └─────────────────┘   └──────────────────────────┘ │
└──────────────────────────────────────────────────────┘
                           │
                           ▼
              gitbot / qabot / pmbot / notebot / …
```

---

## Package Layout

```
bots/slackbot/
├── pyproject.toml           # deps: slack_bolt, shared, orchestrator
└── slackbot/
    ├── __init__.py
    ├── app.py               # Entry point: Bolt app setup, starts listener
    ├── handler.py           # Event handlers: app_mention + message.im (DM)
    ├── intent.py            # Rule-based parser → (action, bot, project)
    └── formatter.py         # BotResult → Slack Block Kit blocks
```

### `pyproject.toml` dependencies

```toml
[project]
name = "slackbot"
dependencies = [
  "shared",
  "orchestrator",
  "slack-bolt>=1.23.0,<2",
  "python-dotenv>=1.0.1,<2",
]

[project.scripts]
slackbot = "slackbot.app:main"
```

---

## Interaction Modes

### 1. Direct Message / @mention (interactive)

User messages the bot directly or mentions it in a channel:

```
@devbot analyze myproject
@devbot qabot myproject --since 2026-02-01
@devbot issues myproject
@devbot list projects
@devbot help
```

The bot:
1. Acknowledges immediately (`:thinking_face:` reaction or "Running…" message)
2. Calls `invoke_bot()` (may take several seconds)
3. Posts the formatted report as a threaded reply

### 2. Slash Command (`/wsl`)

Implemented with a strict allowlist for local utility commands:

```text
/wsl ls
/wsl df
/wsl uptime
/wsl whoami
/wsl gitman list
```

The handler executes only these predefined commands and returns output in a code block.

### 3. Scheduled / Proactive Reports (future)

Not yet implemented. Would post bot reports on a schedule to configured channels using `apscheduler` or a simple cron wrapper.

---

## Intent Parsing (`intent.py`)

Rule-based keyword matching — fast, no LLM call needed for standard commands.

```python
@dataclass
class Intent:
    action: str           # "run_bot" | "list" | "help"
    bot: str | None       # "gitbot", "qabot", "pmbot", "notebot", …
    project_name: str | None

def parse_intent(text: str) -> Intent | None:
    # Longest-alias match: "analyze myproject" → Intent("run_bot", "gitbot", "myproject")
    # Returns None for unrecognised input (bot replies with help text)
    ...
```

Aliases (all map to canonical bot names): `git`/`analyze`/`history` → `gitbot`, `qa`/`tests`/`test` → `qabot`, `issues`/`pm`/`sprint` → `pmbot`, `journal` → `journalbot`, `tasks`/`task` → `taskbot`, `habits`/`habit` → `habitbot`, `notes`/`note` → `notebot`.

---

## Formatting (`formatter.py`)

Bot reports are Markdown. Slack uses `mrkdwn` (a subset) and Block Kit.

Strategy:
- **Short summaries** → `mrkdwn` text in a single message block
- **Full reports** → Posted as a file attachment (Slack Files API) so the channel isn't flooded
- **Structured data** → Block Kit sections (e.g., issue counts, test results)

```python
def format_for_slack(result: BotResult) -> list[dict]:
    """Returns a Slack blocks payload."""
    ...
```

Conversion rules:
- `# Heading` → `*Heading*` (bold)
- `**bold**` → `*bold*`
- `` `code` `` → `` `code` ``
- Tables → plain text or simplified format (Slack doesn't render markdown tables)
- Long reports → truncate + "View full report" link to dashboard

---

## Configuration

Add to `.env`:

```env
# Slack Integration
SLACK_BOT_TOKEN=xoxb-...           # Bot OAuth token (required)
SLACK_SIGNING_SECRET=...           # For HTTP mode request verification
SLACK_APP_TOKEN=xapp-...           # For Socket Mode (optional)
SLACKBOT_LOG_LEVEL=INFO            # Optional: DEBUG, INFO, WARNING, ERROR

# Slack channel for proactive reports (optional)
SLACK_REPORTS_CHANNEL=#dev-digest
```

Add to `.env.example`:

```env
# Slack Integration (optional)
SLACK_BOT_TOKEN=              # xoxb-... Bot OAuth token
SLACK_SIGNING_SECRET=         # App signing secret
SLACK_APP_TOKEN=              # xapp-... Socket Mode token (dev only)
SLACKBOT_LOG_LEVEL=INFO       # Optional logger level for slackbot process
SLACK_REPORTS_CHANNEL=        # Default channel for scheduled reports
```

---

## Starting the Bot

```bash
# Set Slack tokens in the repository root `.env`, then:
uv sync
uv run slackbot     # Connects via Socket Mode; Ctrl-C to stop
```

The bot logs `Starting DevBots Slack bot (Socket Mode)` on startup and then listens for events.

---

## Implementation Status

- [x] `bots/slackbot/` package with `pyproject.toml`
- [x] `app.py` — Bolt app setup, `SocketModeHandler`, `main()` entry point
- [x] `handler.py` — `app_mention` + `message.im` (DM) event handlers, threaded replies, hourglass reaction
- [x] `intent.py` — Rule-based keyword/alias parser
- [x] `formatter.py` — Block Kit header + section blocks, `md_to_mrkdwn()` converter
- [x] `.env.example` updated with `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN`
- [x] Slash command `/wsl` with strict command allowlist
- [ ] Scheduled/proactive reports (future)

Not in `bot_registry.py` — slackbot is a transport layer, not a data analyzer.

---

## Slack App Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → Create New App
2. Enable **Socket Mode** (for development/internal use) or configure **Event Subscriptions** with a public URL (production)
3. Subscribe to bot events:
   - `app_mention` — bot is @mentioned in a channel
   - `message.im` — direct message to the bot
4. Add **OAuth Scopes**:
   - `chat:write` — post messages
   - `files:write` — upload report files
   - `reactions:write` — add emoji reactions (acknowledgment)
   - `app_mentions:read`
   - `im:history`
   - `commands` — enables slash commands
5. Install to workspace → copy `SLACK_BOT_TOKEN`
6. Copy `SLACK_SIGNING_SECRET` from Basic Information
7. (Socket Mode) Copy `SLACK_APP_TOKEN` from App-Level Tokens
8. Create slash command `/wsl` in Slack app settings (Socket Mode enabled)

---

## Open Questions

- **Authentication**: Should all Slack users be trusted, or should we restrict to specific Slack user IDs / channels?
- **Report links**: "View full report" references point to `http://localhost:8080` which isn't accessible from Slack. Consider making the dashboard URL configurable via `DEVBOTS_DASHBOARD_URL`.

---

## Related Files

- `bots/orchestrator/orchestrator/bot_invoker.py` — the function Slack handler will call
- `bots/orchestrator/orchestrator/registry.py` — project lookup
- `bots/orchestrator/orchestrator/cli.py` — reference for intent parsing system prompt
- `shared/shared/bot_registry.py` — bot metadata
- `dashboard/api.py` — alternative: call REST API instead of invoking directly
- `docs/architecture.md` — overall system design
