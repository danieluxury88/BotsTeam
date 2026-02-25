"""JournalBot CLI."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

from journalbot.analyzer import get_bot_result
from shared.config import load_env

load_env()

app = typer.Typer(
    name="journalbot",
    help="📓 JournalBot — AI-powered journal and notes analyzer",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    notes_dir: Annotated[Path, typer.Argument(help="Directory containing markdown journal files")],
    since: Annotated[str | None, typer.Option("--since", help="Only entries on or after this date (YYYY-MM-DD)")] = None,
    until: Annotated[str | None, typer.Option("--until", help="Only entries on or before this date (YYYY-MM-DD)")] = None,
    max_files: Annotated[int, typer.Option("--max-files", help="Maximum number of files to read")] = 30,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Save report to this file")] = None,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project name for auto-saving report")] = None,
):
    """
    Analyze personal journal/notes markdown files.

    Examples:\\n
      journalbot ~/Notes/journal\\n
      journalbot ~/Notes/journal --since 2026-02-01\\n
      journalbot ~/Notes/journal --project myjournal
    """
    since_date = date.fromisoformat(since) if since else None
    until_date = date.fromisoformat(until) if until else None

    console.print(f"[cyan]Reading notes from[/cyan] {notes_dir}...")

    result = get_bot_result(
        notes_dir,
        since=since_date,
        until=until_date,
        max_files=max_files,
        project_name=project,
    )

    if result.status != "success":
        console.print(f"[red]Error:[/red] {result.summary}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] {result.summary}")
    console.print()
    console.print(Rule("[dim]JournalBot Report[/dim]"))
    console.print(Markdown(result.markdown_report))

    if output:
        output.write_text(result.markdown_report, encoding="utf-8")
        console.print(f"\n[dim]Report saved to {output}[/dim]")


# Default command when called as `journalbot <path>`
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    notes_dir: Annotated[Path | None, typer.Argument(help="Directory containing markdown journal files")] = None,
):
    """JournalBot — run 'journalbot analyze <path>' or just 'journalbot <path>'."""
    if ctx.invoked_subcommand is None and notes_dir:
        # Called as: journalbot ~/Notes/journal
        result = get_bot_result(notes_dir)
        if result.status != "success":
            console.print(f"[red]Error:[/red] {result.summary}")
            raise typer.Exit(1)
        console.print(Rule("[dim]JournalBot Report[/dim]"))
        console.print(Markdown(result.markdown_report))


if __name__ == "__main__":
    app()
