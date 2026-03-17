"""PageSpeedBot CLI — collect raw PageSpeed Insights data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown

from pagespeedbot.analyzer import DEFAULT_CATEGORIES, DEFAULT_STRATEGIES, get_bot_result
from shared.config import load_env

load_env()

app = typer.Typer(
    name="pagespeedbot",
    help="⚡ PageSpeedBot — PageSpeed Insights collector",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    url: Annotated[str, typer.Argument(help="Public URL to analyze")],
    strategy: Annotated[str, typer.Option("--strategy", help="mobile, desktop, or all")] = "all",
    category: Annotated[list[str] | None, typer.Option("--category", help="Repeatable Lighthouse category override")] = None,
    timeout: Annotated[int, typer.Option("--timeout", help="HTTP timeout in seconds")] = 120,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Save raw JSON to a file")] = None,
):
    strategies = DEFAULT_STRATEGIES if strategy == "all" else (strategy,)
    categories = tuple(category) if category else DEFAULT_CATEGORIES
    result = get_bot_result(url, strategies=strategies, categories=categories, timeout=timeout)

    if result.status in ("error", "failed"):
        console.print(f"[red]Error:[/red] {result.summary}")
        raise typer.Exit(1)

    console.print(Markdown(result.markdown_report))

    if output:
        output.write_text(json.dumps(result.data, indent=2), encoding="utf-8")
        console.print(f"[dim]Saved summary JSON to {output}[/dim]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Argument(help="Public URL to analyze")] = None,
):
    if ctx.invoked_subcommand is None and url:
        analyze(url)


if __name__ == "__main__":
    app()
