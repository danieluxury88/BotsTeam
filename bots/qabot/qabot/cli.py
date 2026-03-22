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
from qabot.generator import generate_test_stubs, write_test_stubs
from qabot.runner import CoverageReport, detect_test_framework, run_tests
from shared.data_manager import save_report

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

    # Auto-save report
    if result.markdown_report:
        full_report = _generate_markdown_report(
            repo_name=repo_path.name,
            repo_path=repo_path,
            max_commits=max_commits,
            framework_info=framework_info,
            analysis=result.markdown_report,
        )
        latest, timestamped = save_report(repo_path.name, "qabot", full_report)
        console.print(f"[green]✓[/green] Report saved to [bold]{latest}[/bold]")
        if timestamped:
            console.print(f"[dim]  Archived: {timestamped}[/dim]")

    if output:
        output_path = output.resolve()
        try:
            output_path.write_text(full_report, encoding="utf-8")
            console.print(f"[green]✓[/green] Also saved to [bold]{output_path}[/bold]")
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
    coverage: Annotated[
        bool,
        typer.Option("--coverage", help="Run tests with coverage reporting"),
    ] = False,
    min_coverage: Annotated[
        float,
        typer.Option("--min-coverage", help="Flag files below this coverage percentage"),
    ] = 80.0,
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
    mode_label = " with coverage" if coverage else ""
    console.print(f"[dim]Command: {' '.join(framework_info.command)}{mode_label}[/dim]")
    console.print()

    result = run_tests(
        repo_path,
        framework_info,
        with_coverage=coverage,
        min_coverage=min_coverage,
    )

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

    if result.coverage is not None:
        console.print()
        _print_coverage_report(result.coverage, min_coverage=min_coverage)

    console.print()

    raise typer.Exit(0 if result.passed else 1)


@app.command()
def generate(
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
    max_stubs: Annotated[
        int,
        typer.Option("--max-stubs", help="Maximum number of test stub files to generate"),
    ] = 3,
    write: Annotated[
        bool,
        typer.Option("--write", help="Write generated test files into the repository"),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Overwrite existing files when used with --write"),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Save generation report to markdown file"),
    ] = None,
):
    """
    Generate test stub files from recent changes.

    Examples:\n
      qabot generate .\n
      qabot generate /path/to/project --max-stubs 2\n
      qabot generate . --write\n
      qabot generate . --output generated-tests.md
    """
    repo_path = repo_path.resolve()

    if not repo_path.exists():
        rprint(f"[red]Error:[/red] Path does not exist: {repo_path}")
        raise typer.Exit(1)

    console.print()
    console.print(Panel(
        f"[bold cyan]QABot[/bold cyan] generating tests for [bold]{repo_path.name}[/bold]\n"
        f"[dim]Path: {repo_path}  •  Commits: {max_commits}  •  Max stubs: {max_stubs}[/dim]",
        border_style="cyan",
    ))
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("Generating test stubs...", total=None)
        try:
            result = generate_test_stubs(
                repo_path,
                max_commits=max_commits,
                model=model,
                max_stubs=max_stubs,
            )
        except Exception as e:
            rprint(f"[red]Generation failed:[/red] {e}")
            raise typer.Exit(1)

    console.print(Markdown(result.markdown_report))
    console.print()

    latest, timestamped = save_report(repo_path.name, "qabot", result.markdown_report)
    console.print(f"[green]✓[/green] Report saved to [bold]{latest}[/bold]")
    if timestamped:
        console.print(f"[dim]  Archived: {timestamped}[/dim]")

    if output:
        output_path = output.resolve()
        try:
            output_path.write_text(result.markdown_report, encoding="utf-8")
            console.print(f"[green]✓[/green] Also saved to [bold]{output_path}[/bold]")
        except Exception as e:
            rprint(f"[yellow]Warning:[/yellow] Could not save report: {e}")

    if write and result.stubs:
        console.print()
        console.print(Rule("[dim]Writing Test Files[/dim]"))
        written, skipped = write_test_stubs(repo_path, result.stubs, overwrite=overwrite)
        for path in written:
            try:
                display_path = path.relative_to(repo_path)
            except ValueError:
                display_path = path
            console.print(f"[green]✓[/green] Wrote [bold]{display_path}[/bold]")
        for message in skipped:
            console.print(f"[yellow]⚠[/yellow] {message}")

    console.print()
    console.print(Rule())
    console.print("[dim]QABot v0.1.0 — powered by Claude[/dim]")
    console.print()


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
    coverage: Annotated[
        bool,
        typer.Option("--coverage", help="Run tests with coverage reporting"),
    ] = False,
    min_coverage: Annotated[
        float,
        typer.Option("--min-coverage", help="Flag files below this coverage percentage"),
    ] = 80.0,
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
    test_result = None
    if not skip_tests and framework_info.name != "none":
        console.print(Rule("[dim]Running Tests[/dim]"))
        mode_label = " with coverage" if coverage else ""
        console.print(f"[dim]Command: {' '.join(framework_info.command)}{mode_label}[/dim]")
        console.print()

        test_result = run_tests(
            repo_path,
            framework_info,
            with_coverage=coverage,
            min_coverage=min_coverage,
        )

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

        if test_result.coverage is not None:
            console.print()
            _print_coverage_report(test_result.coverage, min_coverage=min_coverage)

    # Auto-save report after optional test execution so coverage can be included
    if analysis.markdown_report:
        full_report = _generate_markdown_report(
            repo_name=repo_path.name,
            repo_path=repo_path,
            max_commits=max_commits,
            framework_info=framework_info,
            analysis=analysis.markdown_report,
            test_result=test_result,
            min_coverage=min_coverage,
        )
        latest, timestamped = save_report(repo_path.name, "qabot", full_report)
        console.print()
        console.print(f"[green]✓[/green] Report saved to [bold]{latest}[/bold]")
        if timestamped:
            console.print(f"[dim]  Archived: {timestamped}[/dim]")

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
    test_result=None,
    min_coverage: float = 80.0,
) -> str:
    """Generate a complete markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# 🧪 QABot Test Analysis Report",
        "",
        f"**Repository:** `{repo_name}`  ",
        f"**Path:** `{repo_path}`  ",
        f"**Commits Analyzed:** {max_commits}  ",
        f"**Test Framework:** {framework_info.name}  ",
        f"**Test Files:** {framework_info.test_files_count}  ",
        f"**Generated:** {timestamp}  ",
        "",
        "---",
        "",
        "## AI Test Analysis",
        "",
        analysis,
        "",
    ]

    if test_result is not None:
        lines.extend([
            "---",
            "",
            "## Test Run",
            "",
            f"- Framework: `{test_result.framework}`",
            f"- Passed: {'yes' if test_result.passed else 'no'}",
            f"- Exit Code: {test_result.exit_code}",
            f"- Summary: {test_result.summary}",
            "",
        ])
        if test_result.coverage is not None:
            lines.extend([
                "## Coverage",
                "",
                f"- Generated: {'yes' if test_result.coverage.generated else 'no'}",
                f"- Summary: {test_result.coverage.summary}",
                "",
            ])
            if test_result.coverage.generated:
                lines.extend([
                    f"- Total Coverage: {test_result.coverage.total_percent:.1f}%",
                    f"- Measured Files: {test_result.coverage.measured_files}",
                    f"- Covered Lines: {test_result.coverage.covered_lines}",
                    f"- Total Statements: {test_result.coverage.total_statements}",
                    "",
                ])
                if test_result.coverage.low_coverage_files:
                    lines.extend([
                        f"### Files Below {min_coverage:.1f}%",
                        "",
                    ])
                    for item in test_result.coverage.low_coverage_files[:20]:
                        lines.append(
                            f"- `{item.path}` — {item.percent_covered:.1f}% "
                            f"({item.missing_lines} missing lines)"
                        )
                    lines.append("")

    lines.extend([
        "---",
        "",
        "*Report generated by QABot v0.1.0 — powered by Claude*",
    ])

    return "\n".join(lines)


def _print_coverage_report(coverage_report: CoverageReport, *, min_coverage: float) -> None:
    """Render a compact coverage summary in the terminal."""
    console.print(Rule("[dim]Coverage[/dim]"))
    if coverage_report.generated:
        console.print(f"[green]✓ Coverage:[/green] {coverage_report.summary}")
    else:
        console.print(f"[yellow]⚠ Coverage unavailable:[/yellow] {coverage_report.summary}")

    if not coverage_report.generated or not coverage_report.low_coverage_files:
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("File", style="cyan")
    table.add_column("Coverage", justify="right")
    table.add_column("Missing", justify="right")

    for item in coverage_report.low_coverage_files[:10]:
        table.add_row(
            item.path,
            f"{item.percent_covered:.1f}%",
            str(item.missing_lines),
        )

    console.print()
    console.print(
        f"[dim]Files below {min_coverage:.1f}% coverage "
        f"(showing up to 10):[/dim]"
    )
    console.print(table)


if __name__ == "__main__":
    app()
