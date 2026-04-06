"""TeamsBot CLI — send DevBots notifications into Microsoft Teams."""

from __future__ import annotations

from urllib import error

import typer
from rich.console import Console

from orchestrator.registry import ProjectRegistry
from shared.config import Config, load_env
from teamsbot.client import send_webhook
from teamsbot.formatter import (
    CardFormat,
    build_adaptive_card_payload,
    build_message_card_payload,
    build_saved_report_payload,
)

app = typer.Typer(
    name="teamsbot",
    help="Microsoft Teams notification bridge for DevBots reports.",
    no_args_is_help=True,
)
console = Console()


def _print_payload(payload: dict) -> None:
    console.print_json(data=payload)


def _send_payload(
    payload: dict,
    *,
    webhook_url: str | None,
    timeout: int,
    dry_run: bool,
) -> None:
    if dry_run:
        _print_payload(payload)
        return

    if not webhook_url:
        webhook_url = Config.teams_webhook_url()

    try:
        response = send_webhook(webhook_url, payload, timeout)
    except error.URLError as exc:
        console.print(f"[red]Network error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[bold]Status:[/bold] {response.status_code}")
    console.print(f"[bold]Response:[/bold] {response.body or '(empty response)'}")

    if response.status_code >= 400:
        raise typer.Exit(1)

    console.print("[green]Teams webhook accepted the payload.[/green]")


def _load_project(project_name: str):
    registry = ProjectRegistry()
    project = registry.get_project(project_name)
    if not project:
        console.print(
            f"[red]Project not found:[/red] {project_name}. "
            "Use `uv run orchestrator projects` to check the registry."
        )
        raise typer.Exit(1)
    return project


def _load_latest_report(project_name: str, bot_name: str):
    project = _load_project(project_name)

    report_path = project.get_report_path(bot_name, "latest")
    if not report_path.exists():
        console.print(
            f"[red]Latest report not found:[/red] {report_path}\n"
            f"Run the target bot first, for example `uv run {bot_name} ...` or generate it from the dashboard."
        )
        raise typer.Exit(1)

    return project, report_path, report_path.read_text(encoding="utf-8")


def _resolve_project_channel_webhook(project, channel_name: str | None) -> str | None:
    if not getattr(project, "teams_channels", None):
        return None

    if channel_name:
        channel = project.get_teams_channel(channel_name)
        if not channel:
            available = ", ".join(item.get("name", "") for item in project.teams_channels or [])
            console.print(
                f"[red]Teams channel not found:[/red] {channel_name}\n"
                f"Available channels for {project.name}: {available or '(none)'}"
            )
            raise typer.Exit(1)

        webhook_url = project.get_teams_webhook_url(channel_name)
        if not webhook_url:
            env_var = channel.get("webhook_env_var", "")
            console.print(
                f"[red]Teams webhook env var is not set:[/red] {env_var}\n"
                f"Set {env_var} in your local .env before sending."
            )
            raise typer.Exit(1)
        return webhook_url

    if len(project.teams_channels or []) == 1:
        channel = project.teams_channels[0]
        webhook_url = project.get_teams_webhook_url(channel.get("name"))
        if webhook_url:
            return webhook_url

    return None


@app.command("send-test")
def send_test(
    webhook_url: str | None = typer.Option(None, "--webhook-url", help="Teams webhook/workflow URL"),
    title: str = typer.Option("DevBots Teams test", "--title", help="Card title"),
    message: str = typer.Option(
        "This is a test notification from DevBots TeamsBot.",
        "--message",
        help="Card body text",
    ),
    card_format: CardFormat = typer.Option("adaptive-card", "--format", help="Teams card format"),
    timeout: int | None = typer.Option(None, "--timeout", help="HTTP timeout in seconds"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print payload without sending"),
) -> None:
    """Send a test notification to Microsoft Teams."""
    load_env()
    resolved_timeout = timeout or Config.teams_timeout_seconds()
    payload = (
        build_message_card_payload(title, message, facts=[("Source", "DevBots TeamsBot")])
        if card_format == "message-card"
        else build_adaptive_card_payload(title, message, facts=[("Source", "DevBots TeamsBot")])
    )
    _send_payload(payload, webhook_url=webhook_url, timeout=resolved_timeout, dry_run=dry_run)


@app.command("send-report")
def send_report(
    project: str = typer.Argument(..., help="Registered project name"),
    bot: str = typer.Argument(..., help="Bot whose latest report should be sent"),
    channel: str | None = typer.Option(None, "--channel", help="Configured Teams channel name for the project"),
    webhook_url: str | None = typer.Option(None, "--webhook-url", help="Teams webhook/workflow URL"),
    card_format: CardFormat = typer.Option("adaptive-card", "--format", help="Teams card format"),
    timeout: int | None = typer.Option(None, "--timeout", help="HTTP timeout in seconds"),
    max_chars: int = typer.Option(3500, "--max-chars", min=200, help="Max report body size to include in the card"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print payload without sending"),
) -> None:
    """Send the latest saved report for a project/bot into Microsoft Teams."""
    load_env()
    resolved_timeout = timeout or Config.teams_timeout_seconds()
    project_record, report_path, report_markdown = _load_latest_report(project, bot)
    payload = build_saved_report_payload(
        project_name=project,
        bot_name=bot,
        report_markdown=report_markdown,
        report_path=report_path,
        card_format=card_format,
        max_chars=max_chars,
    )
    resolved_webhook_url = webhook_url or _resolve_project_channel_webhook(project_record, channel)
    _send_payload(payload, webhook_url=resolved_webhook_url, timeout=resolved_timeout, dry_run=dry_run)
