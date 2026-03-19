"""ReportBot CLI — review and improve markdown reports."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

from reportbot.analyzer import get_bot_result
from shared.config import load_env
from shared.models import BotResult

load_env()

app = typer.Typer(
    name="reportbot",
    help="ReportBot - AI-powered markdown report reviewer and improver",
    add_completion=False,
)
console = Console()


def _print_result(result: BotResult) -> None:
    if result.status != "success":
        console.print(f"[red]Error:[/red] {result.summary}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] {result.summary}")
    console.print()
    console.print(Markdown(result.markdown_report))


@app.command()
def review(
    report_file: Annotated[Path, typer.Argument(help="Markdown report file to review")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Save review output to this file"),
    ] = None,
    instructions_file: Annotated[
        Path | None,
        typer.Option(
            "--instructions-file",
            help="Override the default review prompt with a markdown file",
        ),
    ] = None,
):
    """Review a markdown report and return actionable editorial feedback."""
    console.print()
    console.print(
        Panel(
            f"[bold blue]ReportBot[/bold blue] reviewing [bold]{report_file}[/bold]",
            border_style="blue",
        )
    )
    console.print()

    result = get_bot_result(
        report_file,
        mode="review",
        instructions_file=instructions_file,
    )

    console.print(Rule("[dim]Report Review[/dim]"))
    _print_result(result)

    if output and result.status == "success":
        output.write_text(result.markdown_report, encoding="utf-8")
        console.print(f"\n[dim]Review saved to {output}[/dim]")

    console.print()


@app.command()
def improve(
    report_file: Annotated[Path, typer.Argument(help="Markdown report file to improve")],
    in_place: Annotated[
        bool,
        typer.Option("--in-place", help="Overwrite the original report with the improved version"),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Save improved report to this file"),
    ] = None,
    instructions_file: Annotated[
        Path | None,
        typer.Option(
            "--instructions-file",
            help="Override the default improve prompt with a markdown file",
        ),
    ] = None,
):
    """Improve a markdown report while preserving its factual content."""
    console.print()
    console.print(
        Panel(
            f"[bold blue]ReportBot[/bold blue] improving [bold]{report_file}[/bold]",
            border_style="blue",
        )
    )
    console.print()

    result = get_bot_result(
        report_file,
        mode="improve",
        instructions_file=instructions_file,
    )

    console.print(Rule("[dim]Improved Report[/dim]"))
    _print_result(result)

    if result.status == "success":
        if in_place:
            report_file.write_text(result.markdown_report, encoding="utf-8")
            console.print(f"\n[green]✓[/green] Report updated in place: {report_file}")
        elif output:
            output.write_text(result.markdown_report, encoding="utf-8")
            console.print(f"\n[green]✓[/green] Improved report saved to {output}")
        else:
            console.print(
                "\n[dim]Tip: use --in-place to overwrite the original or --output to save elsewhere[/dim]"
            )

    console.print()


if __name__ == "__main__":
    app()
