"""IssueBot CLI — issue analyzer and workload planner (GitLab & GitHub)."""

from __future__ import annotations

from datetime import datetime, timezone
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

import json

from shared.config import Config, load_env
from shared.data_manager import save_report, get_registry_path, get_personal_registry_path
from shared.gitlab_client import fetch_issues as gitlab_fetch_issues
from shared.gitlab_client import get_issue as gitlab_get_issue
from shared.gitlab_client import update_issue_description as gitlab_update_description
from shared.github_client import fetch_issues as github_fetch_issues
from shared.models import BotStatus, IssueSet, IssueState

from project_manager.analyzer import analyze, plan, review

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


def _load_gitlab_projects() -> list[dict]:
    """Load all projects with GitLab integration from both registries."""
    projects = []
    for registry_path in (get_registry_path(), get_personal_registry_path()):
        if not registry_path.exists():
            continue
        try:
            data = json.loads(registry_path.read_text())
            for name, cfg in data.items():
                if cfg.get("gitlab_project_id"):
                    projects.append({
                        "name": name,
                        "gitlab_project_id": cfg["gitlab_project_id"],
                        "gitlab_url": cfg.get("gitlab_url", "https://gitlab.com"),
                        "description": cfg.get("description", ""),
                    })
        except Exception:
            continue
    return projects


def _resolve_gitlab_project(project_arg: str) -> tuple[str, str]:
    """
    Resolve a project argument to (gitlab_project_id, project_name).

    Accepts:
    - A registered project name (e.g. "UniLi") — looks it up in data/projects.json
    - A raw GitLab project ID or path (e.g. "76261915" or "mygroup/myrepo") — used as-is

    Returns (gitlab_project_id, display_name).
    """
    registry = _load_gitlab_projects()
    name_lower = project_arg.lower()

    # Exact name match first, then case-insensitive
    for p in registry:
        if p["name"].lower() == name_lower:
            return p["gitlab_project_id"], p["name"]

    # Fall back to treating it as a raw GitLab ID/path
    return project_arg, project_arg


def _pick_gitlab_project() -> tuple[str, str]:
    """
    Interactively pick a GitLab project from the registry.
    Returns (gitlab_project_id, project_name).
    Exits with error if no GitLab projects are registered.
    """
    registry = _load_gitlab_projects()

    if not registry:
        rprint(
            "[red]No GitLab projects found in registry.[/red]\n"
            "Add a project with [bold]gitlab_project_id[/bold] to [bold]data/projects.json[/bold], "
            "or pass [bold]--project[/bold] explicitly."
        )
        raise typer.Exit(1)

    if len(registry) == 1:
        p = registry[0]
        console.print(
            f"[dim]Using project:[/dim] [bold]{p['name']}[/bold] "
            f"[dim]({p['gitlab_project_id']})[/dim]"
        )
        return p["gitlab_project_id"], p["name"]

    # Multiple projects — show a numbered menu
    console.print("\n[bold]Available GitLab projects:[/bold]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("#", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("ID", style="dim")
    table.add_column("Description", style="dim")
    for i, p in enumerate(registry, 1):
        table.add_row(str(i), p["name"], p["gitlab_project_id"], p["description"])
    console.print(table)
    console.print()

    choice = typer.prompt(f"Select project [1-{len(registry)}]", default="1")
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(registry)):
            raise ValueError
    except ValueError:
        rprint(f"[red]Invalid selection:[/red] {choice}")
        raise typer.Exit(1)

    p = registry[idx]
    return p["gitlab_project_id"], p["name"]


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

    # Auto-save to data/{project}/reports/pmbot/
    if result.report_md:
        latest, timestamped = save_report(
            issue_set.project_name, "pmbot", result.report_md,
        )
        console.print(f"\n[green]✓[/green] Report saved to [bold]{latest}[/bold]")
        if timestamped:
            console.print(f"[dim]  Archived: {timestamped}[/dim]")

    if output:
        output.write_text(result.report_md)
        console.print(f"[green]✓[/green] Also saved to [bold]{output}[/bold]")

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

    # Auto-save to data/{project}/reports/pmbot/
    if result.report_md:
        latest, timestamped = save_report(
            issue_set.project_name, "pmbot", result.report_md,
        )
        console.print(f"\n[green]✓[/green] Report saved to [bold]{latest}[/bold]")
        if timestamped:
            console.print(f"[dim]  Archived: {timestamped}[/dim]")

    if output:
        output.write_text(result.report_md)
        console.print(f"[green]✓[/green] Also saved to [bold]{output}[/bold]")

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


# ── review command ────────────────────────────────────────────────────────────

@app.command("review")
def review_descriptions(
    project: Annotated[
        str,
        typer.Option(
            "--project", "-p",
            help='Project name from registry (e.g. "UniLi"), or raw GitLab ID/path. '
                 'If omitted, picks from registered GitLab projects.',
        ),
    ] = "",
    state: Annotated[
        str,
        typer.Option("--state", "-s", help="Issue state filter: open | closed | all"),
    ] = "open",
    max_issues: Annotated[
        int,
        typer.Option("--max", "-n", help="Max issues to review"),
    ] = 50,
    issue_iid: Annotated[
        int | None,
        typer.Option("--issue", "-i", help="Review a single issue by its IID (e.g. 36)"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show suggestions without updating GitLab"),
    ] = False,
    output: OutputOpt = None,
):
    """
    AI-powered issue description reviewer (GitLab only).

    Shows improved descriptions for each issue and optionally updates them
    in GitLab after interactive confirmation.

    If --project is omitted, picks from your registered GitLab projects.
    Use --issue to review a single issue by its IID.

    Examples:\n
      issuebot review                          (pick from registry)\n
      issuebot review --project UniLi          (by registered name)\n
      issuebot review --project UniLi --issue 36\n
      issuebot review --project UniLi --dry-run\n
      issuebot review --project UniLi --state all --max 20
    """
    # Resolve project from registry or prompt user to pick
    if project:
        gitlab_project_id, project_name = _resolve_gitlab_project(project)
    else:
        gitlab_project_id, project_name = _pick_gitlab_project()

    state_map = {"open": IssueState.OPEN, "closed": IssueState.CLOSED, "all": IssueState.ALL}
    issue_state = state_map.get(state, IssueState.OPEN)

    scope_label = f"issue #{issue_iid}" if issue_iid else f"{state} issues (max {max_issues})"
    console.print()
    console.print(Panel(
        f"[bold yellow]IssueBot[/bold yellow] → [bold cyan]Description Reviewer[/bold cyan] "
        f"for [bold]{project_name}[/bold]\n"
        f"[dim]{scope_label}"
        + ("  •  [bold red]DRY RUN[/bold red]" if dry_run else "")
        + "[/dim]",
        border_style="yellow",
    ))
    console.print()

    if issue_iid is not None:
        # Single-issue mode
        try:
            with _spinner(f"Fetching issue #{issue_iid} from GitLab..."):
                single = gitlab_get_issue(gitlab_project_id, issue_iid)
        except ValueError as e:
            rprint(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        except Exception as e:
            rprint(f"[red]GitLab API error:[/red] {e}")
            raise typer.Exit(1)
        issue_set = IssueSet(
            project_id=gitlab_project_id,
            project_name=project_name,
            fetched_at=datetime.now(tz=timezone.utc),
            issues=[single],
        )
    else:
        with _spinner(f"Fetching {state} issues from GitLab..."):
            issue_set = _fetch_issues(gitlab_project_id, "", state=issue_state, max_issues=max_issues)

    total = len(issue_set.issues)
    console.print(
        f"[green]✓[/green] Fetched [bold]{total}[/bold] issue(s) to review"
    )

    if total == 0:
        rprint("[yellow]No issues to review.[/yellow]")
        raise typer.Exit(0)

    console.print()
    console.print(Rule("[dim]Generating improved descriptions via Claude[/dim]"))
    with _spinner(f"Reviewing {total} issue description(s)..."):
        suggestions = review(issue_set)

    # Filter out any with no improved description (parse failures)
    valid = [s for s in suggestions if s["improved"]]
    skipped_parse = len(suggestions) - len(valid)
    if skipped_parse:
        console.print(
            f"[yellow]⚠[/yellow]  {skipped_parse} issue(s) could not be processed "
            f"(AI parse error) — skipped."
        )

    console.print(
        f"[green]✓[/green] Generated suggestions for [bold]{len(valid)}[/bold] issue(s)"
    )
    console.print()

    updated_count = 0
    skipped_count = 0
    report_lines: list[str] = [
        f"# Issue Description Review — {issue_set.project_name}\n",
        f"*State: {state} • Issues reviewed: {len(valid)}"
        + (" • DRY RUN (no updates made)" if dry_run else "") + "*\n",
        "---\n",
    ]

    for idx, s in enumerate(valid, 1):
        iid = s["iid"]
        title = s["title"]
        original = s["original"]
        improved = s["improved"]
        web_url = s.get("web_url", "")

        console.print(Rule(f"[bold]#{iid}[/bold] ({idx}/{len(valid)})"))
        console.print(
            f"[bold cyan]#{iid}[/bold cyan] [bold]{title}[/bold]"
            + (f"\n[dim]{web_url}[/dim]" if web_url else "")
        )
        console.print()

        # Original
        console.print(Panel(
            original or "[dim](no description)[/dim]",
            title="[dim]Original[/dim]",
            border_style="dim",
            padding=(1, 2),
        ))

        # Improved
        console.print(Panel(
            Markdown(improved),
            title="[green]Improved[/green]",
            border_style="green",
            padding=(1, 2),
        ))
        console.print()

        # Record for report
        action_taken = "skipped (dry run)" if dry_run else "pending"

        if not dry_run:
            confirm = typer.confirm(f"  Update #{iid} in GitLab?", default=False)
            if confirm:
                try:
                    gitlab_update_description(gitlab_project_id, iid, improved)
                    console.print(f"  [green]✓[/green] #{iid} updated in GitLab\n")
                    updated_count += 1
                    action_taken = "updated"
                except Exception as e:
                    console.print(f"  [red]✗[/red] Failed to update #{iid}: {e}\n")
                    action_taken = f"failed: {e}"
            else:
                console.print(f"  [dim]Skipped #{iid}[/dim]\n")
                skipped_count += 1
                action_taken = "skipped"
        else:
            skipped_count += 1

        report_lines.append(f"## #{iid}: {title}\n")
        report_lines.append(f"**Status:** {action_taken}\n")
        report_lines.append(f"**Original:**\n\n{original or '*(no description)*'}\n")
        report_lines.append(f"**Improved:**\n\n{improved}\n")
        report_lines.append("---\n")

    # Summary
    console.print(Rule("[dim]Review Summary[/dim]"))
    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("Metric", style="dim")
    summary_table.add_column("Value", style="bold")
    summary_table.add_row("Issues reviewed", str(len(valid)))
    if not dry_run:
        summary_table.add_row("Updated in GitLab", str(updated_count))
        summary_table.add_row("Skipped", str(skipped_count))
    else:
        summary_table.add_row("Mode", "dry run — no changes made")
    console.print(summary_table)
    console.print()

    # Save report
    report_md = "\n".join(report_lines)
    latest, timestamped = save_report(issue_set.project_name, "pmbot", report_md)
    console.print(f"[green]✓[/green] Review report saved to [bold]{latest}[/bold]")
    if timestamped:
        console.print(f"[dim]  Archived: {timestamped}[/dim]")

    if output:
        output.write_text(report_md)
        console.print(f"[green]✓[/green] Also saved to [bold]{output}[/bold]")

    console.print()
    console.print(Rule())
    console.print("[dim]IssueBot — Run [bold]issuebot analyze[/bold] for pattern analysis[/dim]")
    console.print()


if __name__ == "__main__":
    app()
