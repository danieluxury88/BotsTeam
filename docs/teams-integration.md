# Microsoft Teams Integration

`teamsbot` is the first DevBots Microsoft Teams integration. This MVP is intentionally outbound-only:

- Send a test card into a Teams workflow/webhook
- Send the latest saved DevBots report for a project/bot

It is not an interactive Teams chat bot yet. Slack remains the only live chat adapter.

## Configuration

Add the Teams webhook or workflow URL to `.env`:

```bash
TEAMS_WEBHOOK_URL=https://...
TEAMS_TIMEOUT_SECONDS=10
TEAMS_BOTSTEAM_REPORTS_WEBHOOK_URL=https://...
```

`TEAMS_WEBHOOK_URL` should come from a Microsoft Teams workflow/webhook endpoint. Do not hardcode it in source files.

For project-scoped delivery, configure Teams channels on the project itself and point each one at an env var. The dashboard project form accepts one entry per line:

```text
Reports | TEAMS_BOTSTEAM_REPORTS_WEBHOOK_URL
Alerts | TEAMS_BOTSTEAM_ALERTS_WEBHOOK_URL
```

## Usage

Send a test message:

```bash
uv run teamsbot send-test
```

Preview the JSON payload without sending:

```bash
uv run teamsbot send-test --dry-run
```

Send the latest saved report for a project and bot:

```bash
uv run teamsbot send-report BotsTeam gitbot
uv run teamsbot send-report BotsTeam gitbot --channel Reports
uv run teamsbot send-report UniLi pmbot --format message-card
```

If the report does not exist yet, generate it first through the bot CLI or dashboard.

Webhook resolution order for `send-report` is:

1. `--webhook-url`
2. `--channel <name>` from the project's configured Teams channels
3. The project's only configured Teams channel, if there is exactly one
4. Global `TEAMS_WEBHOOK_URL`

## Design Notes

- Uses global `.env` configuration instead of per-project Teams settings.
- Reuses the existing report storage layout under `data/{project}/reports/{bot}/latest.md`.
- Keeps Teams-specific transport and formatting isolated inside `bots/teamsbot/`.

## Next Steps

When we decide to go beyond notifications, the next correct step is not to expand webhook logic. It is to extract a channel-agnostic chat dispatch layer from SlackBot and build a real Teams adapter on top of it.
