"""NoteBot CLI — note-taking and organisation assistant."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

from notebot.analyzer import get_bot_result, improve_note
from shared.config import load_env

load_env()

app = typer.Typer(
    name="notebot",
    help="📝 NoteBot — AI-powered note-taking and organisation assistant",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    notes_dir: Annotated[Path, typer.Argument(help="Directory containing markdown note files")],
    since: Annotated[str | None, typer.Option("--since", help="Only notes modified on or after this date (YYYY-MM-DD)")] = None,
    until: Annotated[str | None, typer.Option("--until", help="Only notes modified on or before this date (YYYY-MM-DD)")] = None,
    max_files: Annotated[int, typer.Option("--max-files", help="Maximum number of files to read")] = 50,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Save report to this file")] = None,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project name for auto-saving report")] = None,
):
    """
    Analyse a directory of markdown notes.

    Produces a structured report covering key themes, action items,
    organisation suggestions, and knowledge gaps.

    Examples:\\n
      notebot analyze data/myproject/notes/\\n
      notebot analyze ~/Notes --since 2026-02-01\\n
      notebot analyze data/myproject/notes/ --project myproject
    """
    since_date = date.fromisoformat(since) if since else None
    until_date = date.fromisoformat(until) if until else None

    console.print()
    console.print(Panel(
        f"[bold yellow]NoteBot[/bold yellow] analysing [bold]{notes_dir}[/bold]",
        border_style="yellow",
    ))
    console.print()
    console.print(f"[cyan]Reading notes from[/cyan] {notes_dir}...")

    result = get_bot_result(
        notes_dir,
        mode="analyze",
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
    console.print(Rule("[dim]NoteBot Analysis[/dim]"))
    console.print(Markdown(result.markdown_report))

    if project:
        console.print(f"\n[dim]Report auto-saved for project '{project}'[/dim]")

    if output:
        output.write_text(result.markdown_report, encoding="utf-8")
        console.print(f"[dim]Report also saved to {output}[/dim]")

    console.print()


@app.command()
def improve(
    note_file: Annotated[Path, typer.Argument(help="Markdown note file to improve")],
    in_place: Annotated[bool, typer.Option("--in-place", help="Overwrite the original file with the improved version")] = False,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Save improved note to this file")] = None,
):
    """
    Improve a single markdown note using AI.

    Claude rewrites the note with better structure, headings, and clarity
    while preserving all original content.

    Examples:\\n
      notebot improve meeting-notes.md\\n
      notebot improve ideas.md --in-place\\n
      notebot improve rough-draft.md --output polished.md
    """
    if not note_file.exists():
        console.print(f"[red]Error:[/red] File not found: {note_file}")
        raise typer.Exit(1)

    original = note_file.read_text(encoding="utf-8")
    console.print(f"[cyan]Improving note:[/cyan] {note_file.name}...")

    improved = improve_note(original, title=note_file.name)

    console.print(Rule("[dim]Improved Note[/dim]"))
    console.print(Markdown(improved))

    if in_place:
        note_file.write_text(improved, encoding="utf-8")
        console.print(f"\n[green]✓[/green] File updated in place: {note_file}")
    elif output:
        output.write_text(improved, encoding="utf-8")
        console.print(f"\n[green]✓[/green] Improved note saved to {output}")
    else:
        console.print("\n[dim]Tip: use --in-place to overwrite the original or --output to save elsewhere[/dim]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    notes_dir: Annotated[Path | None, typer.Argument(help="Directory containing markdown note files")] = None,
):
    """NoteBot — run 'notebot analyze <path>' or just 'notebot <path>'."""
    if ctx.invoked_subcommand is None and notes_dir:
        result = get_bot_result(notes_dir)
        if result.status != "success":
            console.print(f"[red]Error:[/red] {result.summary}")
            raise typer.Exit(1)
        console.print(Rule("[dim]NoteBot Analysis[/dim]"))
        console.print(Markdown(result.markdown_report))


if __name__ == "__main__":
    app()
