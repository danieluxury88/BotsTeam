"""TaskBot CLI."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

from taskbot.analyzer import get_bot_result
from shared.config import load_env

load_env()

app = typer.Typer(
    name="taskbot",
    help="✅ TaskBot — AI-powered personal task list analyzer",
    add_completion=False,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    task_source: Annotated[Path | None, typer.Argument(help="Task file or directory")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Save report to this file")] = None,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project name for auto-saving report")] = None,
):
    """
    Analyze personal task lists and generate productivity insights.

    Examples:\\n
      taskbot ~/Notes/tasks.md\\n
      taskbot ~/Notes/tasks/\\n
      taskbot ~/Notes/tasks.md --project mytasks
    """
    if ctx.invoked_subcommand is not None:
        return

    if not task_source:
        console.print("[red]Error:[/red] Please provide a task file or directory path.")
        raise typer.Exit(1)

    console.print(f"[cyan]Reading tasks from[/cyan] {task_source}...")

    result = get_bot_result(task_source, project_name=project)

    if result.status != "success":
        console.print(f"[red]Error:[/red] {result.summary}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] {result.summary}")
    console.print()
    console.print(Rule("[dim]TaskBot Report[/dim]"))
    console.print(Markdown(result.markdown_report))

    if output:
        output.write_text(result.markdown_report, encoding="utf-8")
        console.print(f"\n[dim]Report saved to {output}[/dim]")


if __name__ == "__main__":
    app()
