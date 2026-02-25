"""HabitBot CLI."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

from habitbot.analyzer import get_bot_result
from shared.config import load_env

load_env()

app = typer.Typer(
    name="habitbot",
    help="🔄 HabitBot — AI-powered habit and goal tracking analyzer",
    add_completion=False,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    habit_source: Annotated[Path | None, typer.Argument(help="Habit log file (.csv or .md)")] = None,
    since: Annotated[str | None, typer.Option("--since", help="From date (YYYY-MM-DD)")] = None,
    until: Annotated[str | None, typer.Option("--until", help="To date (YYYY-MM-DD)")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Save report to this file")] = None,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project name for auto-saving report")] = None,
):
    """
    Analyze personal habit tracking data and surface consistency insights.

    Examples:\\n
      habitbot ~/Notes/habits.csv\\n
      habitbot ~/Notes/habits.md --since 2026-02-01\\n
      habitbot ~/Notes/habits.csv --project myhabits
    """
    if ctx.invoked_subcommand is not None:
        return

    if not habit_source:
        console.print("[red]Error:[/red] Please provide a habit log file path.")
        raise typer.Exit(1)

    since_date = date.fromisoformat(since) if since else None
    until_date = date.fromisoformat(until) if until else None

    console.print(f"[cyan]Reading habit data from[/cyan] {habit_source}...")

    result = get_bot_result(
        habit_source,
        since=since_date,
        until=until_date,
        project_name=project,
    )

    if result.status != "success":
        console.print(f"[red]Error:[/red] {result.summary}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] {result.summary}")
    console.print()
    console.print(Rule("[dim]HabitBot Report[/dim]"))
    console.print(Markdown(result.markdown_report))

    if output:
        output.write_text(result.markdown_report, encoding="utf-8")
        console.print(f"\n[dim]Report saved to {output}[/dim]")


if __name__ == "__main__":
    app()
