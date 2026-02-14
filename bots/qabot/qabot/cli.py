"""QABot CLI — AI-powered test suggestion and execution."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table

from qabot.analyzer import analyze_changes_for_testing
from qabot.runner import detect_test_framework, run_tests
from shared.models import BotResult

app = typer.Typer(
    name="qabot",
    help="🧪 QABot — AI-powered test suggestion and execution",
    add_completion=False,
)
console = Console()


@app.command()
def suggest(
    repo_path: Annotated[
        Path,
        typer.Argument(help="Path to the git repository to analyze"),
    ] = Path("."),
    max_commits: Annotated[
        int,
        typer.Option("--max-commits", "-n", help="Maximum number of commits to analyze"),
    ] = 50,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Claude model to use (overrides .env)"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Save report to markdown file"),
    ] = None,
):
    """
    Analyze recent changes and suggest what to test.

    Examples:\n
      qabot suggest .\n
      qabot suggest /path/to/project --max-commits 20\n
      qabot suggest . --output test-plan.md
    """
    repo_path = repo_path.resolve()

    if not repo_path.exists():
        rprint(f"[red]Error:[/red] Path does not exist: {repo_path}")
        raise typer.Exit(1)

    console.print()
    console.print(Panel(
        f"[bold cyan]QABot[/bold cyan] analyzing [bold]{repo_path.name}[/bold]\n"
        f"[dim]Path: {repo_path}  •  Commits: {max_commits}[/dim]",
        border_style="cyan",
    ))
    console.print()

    # Detect test framework
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("Detecting test framework...", total=None)
        framework_info = detect_test_framework(repo_path)

    if framework_info.name != "none":
        console.print(
            f"[green]✓[/green] Detected [bold]{framework_info.name}[/bold] "
            f"with [bold]{framework_info.test_files_count}[/bold] test files"
        )
    else:
        console.print("[yellow]⚠[/yellow] No test framework detected")
    console.print()

    # Analyze changes
    console.print(Rule("[dim]Analyzing Changes[/dim]"))
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("Asking Claude what to test...", total=None)
        try:
            result = analyze_changes_for_testing(repo_path, max_commits=max_commits, model=model)
        except Exception as e:
            rprint(f"[red]Analysis failed:[/red] {e}")
            raise typer.Exit(1)

    console.print(Markdown(result.markdown_report))
    console.print()

    # Save report if requested
    if output:
        output_path = output.resolve()
        full_report = _generate_markdown_report(
            repo_name=repo_path.name,
            repo_path=repo_path,
            max_commits=max_commits,
            framework_info=framework_info,
            analysis=result.markdown_report,
        )
        try:
            output_path.write_text(full_report, encoding="utf-8")
            console.print(f"[green]✓[/green] Report saved to [bold]{output_path}[/bold]")
        except Exception as e:
            rprint(f"[yellow]Warning:[/yellow] Could not save report: {e}")
        console.print()

    console.print(Rule())
    console.print("[dim]QABot v0.1.0 — powered by Claude[/dim]")
    console.print()


@app.command()
def run(
    repo_path: Annotated[
        Path,
        typer.Argument(help="Path to the repository to test"),
    ] = Path("."),
):
    """
    Detect and run tests in the repository.

    Examples:\n
      qabot run .\n
      qabot run /path/to/project
    """
    repo_path = repo_path.resolve()

    if not repo_path.exists():
        rprint(f"[red]Error:[/red] Path does not exist: {repo_path}")
        raise typer.Exit(1)

    console.print()
    console.print(Panel(
        f"[bold cyan]QABot[/bold cyan] running tests in [bold]{repo_path.name}[/bold]\n"
        f"[dim]Path: {repo_path}[/dim]",
        border_style="cyan",
    ))
    console.print()

    # Detect framework
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("Detecting test framework...", total=None)
        framework_info = detect_test_framework(repo_path)

    if framework_info.name == "none":
        rprint("[red]Error:[/red] No test framework or test files detected")
        raise typer.Exit(1)

    console.print(
        f"[green]✓[/green] Detected [bold]{framework_info.name}[/bold] "
        f"with [bold]{framework_info.test_files_count}[/bold] test files"
    )
    console.print()

    # Run tests
    console.print(Rule("[dim]Running Tests[/dim]"))
    console.print(f"[dim]Command: {' '.join(framework_info.command)}[/dim]")
    console.print()

    result = run_tests(repo_path, framework_info)

    # Show output
    if result.stdout:
        console.print(result.stdout)

    if result.stderr:
        console.print(f"[red]{result.stderr}[/red]")

    console.print()
    console.print(Rule())

    # Show summary
    if result.passed:
        console.print(f"[green]✓ Tests passed:[/green] {result.summary}")
    else:
        console.print(f"[red]✗ Tests failed:[/red] {result.summary}")

    console.print()

    raise typer.Exit(0 if result.passed else 1)


@app.command()
def full(
    repo_path: Annotated[
        Path,
        typer.Argument(help="Path to the repository"),
    ] = Path("."),
    max_commits: Annotated[
        int,
        typer.Option("--max-commits", "-n", help="Maximum number of commits to analyze"),
    ] = 50,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Claude model to use"),
    ] = None,
    skip_tests: Annotated[
        bool,
        typer.Option("--skip-tests", help="Only analyze, don't run tests"),
    ] = False,
):
    """
    Full QA workflow: suggest what to test, then run tests.

    Examples:\n
      qabot full .\n
      qabot full /path/to/project --max-commits 20\n
      qabot full . --skip-tests
    """
    repo_path = repo_path.resolve()

    if not repo_path.exists():
        rprint(f"[red]Error:[/red] Path does not exist: {repo_path}")
        raise typer.Exit(1)

    console.print()
    console.print(Panel(
        f"[bold cyan]QABot[/bold cyan] full analysis of [bold]{repo_path.name}[/bold]\n"
        f"[dim]Path: {repo_path}  •  Commits: {max_commits}[/dim]",
        border_style="cyan",
    ))
    console.print()

    # Step 1: Detect test framework
    framework_info = detect_test_framework(repo_path)
    if framework_info.name != "none":
        console.print(
            f"[green]✓[/green] Detected [bold]{framework_info.name}[/bold] "
            f"with [bold]{framework_info.test_files_count}[/bold] test files"
        )
    else:
        console.print("[yellow]⚠[/yellow] No test framework detected")
    console.print()

    # Step 2: Analyze changes
    console.print(Rule("[dim]Test Suggestions[/dim]"))
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("Asking Claude what to test...", total=None)
        try:
            analysis = analyze_changes_for_testing(repo_path, max_commits=max_commits, model=model)
        except Exception as e:
            rprint(f"[red]Analysis failed:[/red] {e}")
            raise typer.Exit(1)

    console.print(Markdown(analysis.markdown_report))
    console.print()

    # Step 3: Run tests (if not skipped and framework exists)
    if not skip_tests and framework_info.name != "none":
        console.print(Rule("[dim]Running Tests[/dim]"))
        console.print(f"[dim]Command: {' '.join(framework_info.command)}[/dim]")
        console.print()

        test_result = run_tests(repo_path, framework_info)

        if test_result.stdout:
            console.print(test_result.stdout)

        if test_result.stderr:
            console.print(f"[yellow]{test_result.stderr}[/yellow]")

        console.print()
        console.print(Rule())

        if test_result.passed:
            console.print(f"[green]✓ Tests passed:[/green] {test_result.summary}")
        else:
            console.print(f"[red]✗ Tests failed:[/red] {test_result.summary}")

    console.print()
    console.print(Rule())
    console.print("[dim]QABot v0.1.0 — powered by Claude[/dim]")
    console.print()


def _generate_markdown_report(
    repo_name: str,
    repo_path: Path,
    max_commits: int,
    framework_info,
    analysis: str,
) -> str:
    """Generate a complete markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# 🧪 QABot Test Analysis Report",
        f"",
        f"**Repository:** `{repo_name}`  ",
        f"**Path:** `{repo_path}`  ",
        f"**Commits Analyzed:** {max_commits}  ",
        f"**Test Framework:** {framework_info.name}  ",
        f"**Test Files:** {framework_info.test_files_count}  ",
        f"**Generated:** {timestamp}  ",
        f"",
        f"---",
        f"",
        f"## AI Test Analysis",
        f"",
        analysis,
        f"",
        f"---",
        f"",
        f"*Report generated by QABot v0.1.0 — powered by Claude*",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    app()
