"""IssueBot CLI — issue analyzer and workload planner (GitLab & GitHub)."""

from __future__ import annotations

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
from rich.text import Text

from shared.config import Config, load_env
from shared.gitlab_client import fetch_issues as gitlab_fetch_issues
from shared.github_client import fetch_issues as github_fetch_issues
from shared.models import BotStatus, IssueSet, IssueState

from project_manager.analyzer import analyze, plan

load_env()

app = typer.Typer(
    name="issuebot",
    help="📋 IssueBot — issue analyzer and workload planner (GitLab & GitHub)",
    add_completion=False,
)
console = Console()

# ── Shared option types ───────────────────────────────────────────────────────

ProjectArg = Annotated[
    str,
    typer.Option(
        "--project", "-p",
        help='GitLab project ID or path (e.g. "42" or "mygroup/myrepo"). '
             'Falls back to GITLAB_PROJECT_ID in .env.',
    ),
]

GitHubRepoOpt = Annotated[
    str,
    typer.Option(
        "--github-repo", "-gh",
        help='GitHub repository "owner/repo". When set, fetches from GitHub instead of GitLab.',
    ),
]

OutputOpt = Annotated[
    Path | None,
    typer.Option("--output", "-o", help="Save markdown report to file"),
]

MaxOpt = Annotated[
    int,
    typer.Option("--max", "-n", help="Max issues to fetch (default: 200)"),
]


def _resolve_project(project: str) -> str:
    resolved = project or Config.gitlab_project_id()
    if not resolved:
        rprint(
            "[red]Error:[/red] No project specified.\n"
            "Use [bold]--project mygroup/myrepo[/bold] or set "
            "[bold]GITLAB_PROJECT_ID[/bold] in your .env file."
        )
        raise typer.Exit(1)
    return resolved


def _fetch_issues(
    project: str,
    github_repo: str,
    state: IssueState,
    max_issues: int,
) -> IssueSet:
    """Fetch issues from GitHub or GitLab depending on which option is set."""
    if github_repo:
        try:
            return github_fetch_issues(github_repo, state=state, max_issues=max_issues)
        except EnvironmentError as e:
            rprint(f"[red]Config error:[/red] {e}")
            raise typer.Exit(1)
        except ValueError as e:
            rprint(f"[red]Repository error:[/red] {e}")
            raise typer.Exit(1)
        except Exception as e:
            rprint(f"[red]GitHub API error:[/red] {e}")
            raise typer.Exit(1)
    else:
        project = _resolve_project(project)
        try:
            return gitlab_fetch_issues(project, state=state, max_issues=max_issues)
        except EnvironmentError as e:
            rprint(f"[red]Config error:[/red] {e}")
            raise typer.Exit(1)
        except ValueError as e:
            rprint(f"[red]Project error:[/red] {e}")
            raise typer.Exit(1)
        except Exception as e:
            rprint(f"[red]GitLab API error:[/red] {e}")
            raise typer.Exit(1)


def _spinner(msg: str) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    )


# ── list command ─────────────────────────────────────────────────────────────

@app.command("list")
def list_issues(
    project: ProjectArg = "",
    github_repo: GitHubRepoOpt = "",
    state: Annotated[
        str,
        typer.Option("--state", "-s", help="Filter: open | closed | all"),
    ] = "all",
    max_issues: MaxOpt = 200,
    label: Annotated[
        str,
        typer.Option("--label", "-l", help="Filter by label"),
    ] = "",
    assignee: Annotated[
        str,
        typer.Option("--assignee", "-a", help="Filter by assignee username"),
    ] = "",
):
    """
    Fetch and display issues in a Rich table.

    Examples:\n
      issuebot list --project mygroup/myrepo\n
      issuebot list --github-repo owner/repo --state open\n
      issuebot list -p mygroup/myrepo --label bug --state open
    """
    source_name = github_repo or _resolve_project(project)

    state_map = {"open": IssueState.OPEN, "closed": IssueState.CLOSED, "all": IssueState.ALL}
    issue_state = state_map.get(state, IssueState.ALL)

    console.print()
    console.print(Panel(
        f"[bold yellow]IssueBot[/bold yellow] listing issues for [bold]{source_name}[/bold]\n"
        f"[dim]State: {state}  •  Max: {max_issues}[/dim]",
        border_style="yellow",
    ))
    console.print()

    source_label = "GitHub" if github_repo else "GitLab"
    with _spinner(f"Fetching {state} issues from {source_label}..."):
        issue_set = _fetch_issues(project, github_repo, state=issue_state, max_issues=max_issues)

    issues = issue_set.issues

    # Apply local filters
    if label:
        issues = [i for i in issues if label in i.labels]
    if assignee:
        issues = [i for i in issues if assignee in i.assignees]

    console.print(
        f"[green]✓[/green] Fetched [bold]{len(issue_set.issues)}[/bold] issues "
        f"([bold]{len(issue_set.open_issues)}[/bold] open, "
        f"[bold]{len(issue_set.closed_issues)}[/bold] closed)"
    )
    if label or assignee:
        console.print(f"[dim]Filtered to {len(issues)} issues[/dim]")
    console.print()

    if not issues:
        rprint("[yellow]No issues match your filters.[/yellow]")
        raise typer.Exit(0)

    # Build table
    table = Table(
        show_header=True,
        header_style="bold yellow",
        expand=True,
        row_styles=["", "dim"],
    )
    table.add_column("#", style="cyan", no_wrap=True, width=6)
    table.add_column("Title", ratio=4)
    table.add_column("State", width=8)
    table.add_column("Labels", ratio=2)
    table.add_column("Assignee", width=16)
    table.add_column("Age", justify="right", width=8)

    for i in issues:
        state_text = Text("open", style="green") if i.state.value == "opened" else Text("closed", style="dim")
        label_str = ", ".join(i.labels[:3]) + ("…" if len(i.labels) > 3 else "")
        assignee_str = ", ".join(i.assignees[:2]) or "—"
        age_str = f"{i.age_days}d"

        table.add_row(
            f"#{i.iid}",
            i.title,
            state_text,
            label_str,
            assignee_str,
            age_str,
        )

    console.print(table)
    console.print()


# ── analyze command ───────────────────────────────────────────────────────────

@app.command("analyze")
def analyze_issues(
    project: ProjectArg = "",
    github_repo: GitHubRepoOpt = "",
    max_issues: MaxOpt = 200,
    output: OutputOpt = None,
):
    """
    AI-powered issue analysis: patterns, recurring problems, team workload.

    Examples:\n
      issuebot analyze --project mygroup/myrepo\n
      issuebot analyze --github-repo owner/repo\n
      issuebot analyze -p mygroup/myrepo --output analysis.md
    """
    source_name = github_repo or _resolve_project(project)

    console.print()
    console.print(Panel(
        f"[bold yellow]IssueBot[/bold yellow] analyzing [bold]{source_name}[/bold]",
        border_style="yellow",
    ))
    console.print()

    source_label = "GitHub" if github_repo else "GitLab"
    with _spinner(f"Fetching all issues from {source_label}..."):
        issue_set = _fetch_issues(project, github_repo, state=IssueState.ALL, max_issues=max_issues)

    console.print(
        f"[green]✓[/green] Fetched [bold]{len(issue_set.issues)}[/bold] issues "
        f"({len(issue_set.open_issues)} open, {len(issue_set.closed_issues)} closed)"
    )
    console.print()

    console.print(Rule("[dim]AI Analysis[/dim]"))
    with _spinner("Asking Claude to analyze issue patterns..."):
        result = analyze(issue_set)

    if result.status == BotStatus.FAILED:
        rprint(f"[red]Analysis failed:[/red] {result.errors}")
        raise typer.Exit(1)

    console.print(Markdown(result.report_md))

    if output:
        output.write_text(result.report_md)
        console.print(f"\n[green]✓[/green] Analysis saved to [bold]{output}[/bold]")

    console.print()
    console.print(Rule())
    console.print("[dim]IssueBot v0.1.0 — Run [bold]issuebot plan[/bold] to generate a sprint plan[/dim]")
    console.print()


# ── plan command ──────────────────────────────────────────────────────────────

@app.command("plan")
def plan_workload(
    project: ProjectArg = "",
    github_repo: GitHubRepoOpt = "",
    max_issues: MaxOpt = 100,
    output: OutputOpt = None,
    weeks: Annotated[
        int,
        typer.Option("--weeks", "-w", help="Number of sprint weeks to plan for"),
    ] = 4,
):
    """
    Generate an AI sprint plan: prioritize open issues, estimate effort,
    and schedule a weekly workload.

    Examples:\n
      issuebot plan --project mygroup/myrepo\n
      issuebot plan --github-repo owner/repo\n
      issuebot plan -p mygroup/myrepo --weeks 2 --output sprint.md
    """
    source_name = github_repo or _resolve_project(project)

    console.print()
    console.print(Panel(
        f"[bold yellow]IssueBot[/bold yellow] → [bold magenta]Sprint Planner[/bold magenta] "
        f"for [bold]{source_name}[/bold]\n"
        f"[dim]Planning {weeks} week(s) of open issues[/dim]",
        border_style="yellow",
    ))
    console.print()

    source_label = "GitHub" if github_repo else "GitLab"
    with _spinner(f"Fetching open issues from {source_label}..."):
        issue_set = _fetch_issues(project, github_repo, state=IssueState.OPEN, max_issues=max_issues)

    open_count = len(issue_set.open_issues)
    console.print(f"[green]✓[/green] Fetched [bold]{open_count}[/bold] open issues")

    if open_count == 0:
        rprint("[yellow]No open issues — nothing to plan![/yellow]")
        raise typer.Exit(0)

    console.print()
    console.print(Rule("[dim]Generating Sprint Plan[/dim]"))
    with _spinner("Asking Claude to prioritize and schedule issues..."):
        plan_obj, result = plan(issue_set)

    if result.status == BotStatus.FAILED:
        rprint(f"[red]Planning failed:[/red] {result.errors}")
        raise typer.Exit(1)

    console.print(Markdown(result.report_md))

    if output:
        output.write_text(result.report_md)
        console.print(f"\n[green]✓[/green] Sprint plan saved to [bold]{output}[/bold]")

    # Summary stats
    console.print()
    console.print(Rule("[dim]Plan Summary[/dim]"))
    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("Metric", style="dim")
    summary_table.add_column("Value", style="bold")

    by_priority = {}
    for pi in plan_obj.planned_issues:
        key = pi.priority.value
        by_priority[key] = by_priority.get(key, 0) + 1

    summary_table.add_row("Open issues planned", str(len(plan_obj.planned_issues)))
    summary_table.add_row("Weeks scheduled", str(len(plan_obj.by_week)))
    for prio in ["critical", "high", "normal", "low"]:
        if by_priority.get(prio):
            summary_table.add_row(f"{prio.capitalize()} priority", str(by_priority[prio]))
    if plan_obj.warnings:
        summary_table.add_row("Warnings", str(len(plan_obj.warnings)))

    console.print(summary_table)
    console.print()
    console.print(Rule())
    console.print("[dim]IssueBot v0.1.0 — Run [bold]issuebot analyze[/bold] for pattern analysis[/dim]")
    console.print()


if __name__ == "__main__":
    app()
