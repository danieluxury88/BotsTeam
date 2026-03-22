"""Conversational orchestrator CLI."""

import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table

from orchestrator.registry import ProjectRegistry
from orchestrator.router import process_user_request
from shared.config import load_env
from shared.models import ProjectScope

load_env()

app = typer.Typer(
    name="orchestrator",
    help="🤖 DevBot Orchestrator — Conversational interface to all bots",
    add_completion=False,
)
console = Console()


def _is_success_status(status: object) -> bool:
    value = getattr(status, "value", status)
    return value == "success"


def _split_multi_values(values: list[str] | tuple[str, ...] | None) -> list[str]:
    """Normalize repeated or comma-separated CLI values."""
    if not values:
        return []

    result: list[str] = []
    for value in values:
        for part in value.split(","):
            cleaned = part.strip()
            if cleaned and cleaned not in result:
                result.append(cleaned)
    return result

# ── Shared option types ──────────────────────────────────────────────────────
GitLabProjectIdOpt = Annotated[
    str | None,
    typer.Option("--gitlab-id", "-g", help="GitLab project ID or 'namespace/project'")
]

GitLabUrlOpt = Annotated[
    str | None,
    typer.Option("--gitlab-url", help="GitLab instance URL (self-hosted only)")
]

GitLabTokenOpt = Annotated[
    str | None,
    typer.Option("--gitlab-token", help="Per-project GitLab token (overrides .env)")
]

GitHubRepoOpt = Annotated[
    str | None,
    typer.Option("--github-repo", help="GitHub repository 'owner/repo'")
]

ScopeOpt = Annotated[
    str,
    typer.Option("--scope", "-s", help="Project scope: 'team' (default) or 'personal'")
]


@app.command()
def chat(
    registry_path: Annotated[
        Path | None,
        typer.Option("--registry", "-r", help="Path to project registry JSON"),
    ] = None,
):
    """
    Start a conversational session with the orchestrator.

    Ask it to get bot reports for your projects!

    Examples:\\n
      orchestrator chat\\n

    Then try:\\n
      > get qabot report for uni.li\\n
      > how was my week?\\n
      > check my tasks\\n
      > what projects do you know?
    """
    registry = ProjectRegistry(registry_path)

    console.print()
    console.print(Panel(
        "[bold cyan]DevBot Orchestrator[/bold cyan]\n"
        "[dim]Ask me to get reports from any bot for your projects![/dim]\n\n"
        "Commands: /projects, /add, /remove, /exit",
        border_style="cyan",
    ))
    console.print()

    team_projects = registry.list_by_scope(ProjectScope.TEAM)
    personal_projects = registry.list_by_scope(ProjectScope.PERSONAL)

    if team_projects:
        console.print(f"[green]✓[/green] Team projects: [bold]{', '.join(p.name for p in team_projects)}[/bold]")
    if personal_projects:
        console.print(f"[blue]✓[/blue] Personal projects: [bold]{', '.join(p.name for p in personal_projects)}[/bold]")
    if not team_projects and not personal_projects:
        console.print("[yellow]⚠[/yellow] No projects registered. Use [bold]/add[/bold] to register a project.")
    console.print()

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")

            if not user_input.strip():
                continue

            if user_input.startswith("/"):
                command = user_input[1:].lower().strip()

                if command in ("exit", "quit"):
                    console.print("[dim]Goodbye![/dim]")
                    break
                elif command == "projects":
                    _show_projects(registry)
                    continue
                elif command == "add":
                    _add_project_interactive(registry)
                    continue
                elif command == "remove":
                    name = Prompt.ask("Project name to remove")
                    registry.remove_project(name)
                    console.print(f"[green]✓[/green] Removed project: [bold]{name}[/bold]")
                    continue
                else:
                    console.print(f"[red]Unknown command:[/red] {command}")
                    continue

            console.print()
            outcome = process_user_request(user_input, registry)
            action_plan = outcome.action_plan

            if "explanation" in action_plan:
                console.print(f"[dim]→ {action_plan['explanation']}[/dim]")

            if outcome.error:
                console.print(f"[red]Error:[/red] {outcome.error}")
                console.print("[dim]Try: 'get qabot report for myproject' or 'how was my week?'[/dim]")
                console.print()
                continue

            if action_plan.get("action") == "list_projects":
                _show_projects(registry)
            elif outcome.bot_result:
                bot_name = action_plan.get("bot", "bot")
                project_name = action_plan.get("project", "project")

                console.print(f"[cyan]Running {bot_name} on {project_name}...[/cyan]")
                console.print()

                if _is_success_status(outcome.bot_result.status):
                    console.print(Rule(f"[dim]{bot_name.upper()} Report[/dim]"))
                    console.print(Markdown(outcome.bot_result.markdown_report))
                else:
                    console.print(f"[red]Error:[/red] {outcome.bot_result.summary}")
            else:
                console.print("[yellow]⚠[/yellow] Sorry, I couldn't understand that request.")
                console.print("[dim]Try: 'get qabot report for myproject' or 'how was my week?'[/dim]")

            console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break


def quick_chat() -> None:
    """Launch the default orchestrator chat session directly."""
    chat()


@app.command()
def dashboard(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to serve dashboard on")] = 8080,
    no_generate: Annotated[bool, typer.Option("--no-generate", help="Skip data generation")] = False,
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Don't open browser")] = False,
):
    """
    Launch the DevBots Dashboard web interface.

    Generates data and starts a local web server to view projects, bots, and reports.

    Examples:\\n
      orchestrator dashboard\\n
      orchestrator dashboard --port 3000\\n
      orchestrator dashboard --no-generate
    """
    repo_root = Path(__file__).parent.parent.parent.parent
    dashboard_dir = repo_root / "dashboard"

    if not dashboard_dir.exists():
        console.print("[red]Error:[/red] Dashboard directory not found")
        console.print(f"[dim]Expected: {dashboard_dir}[/dim]")
        raise typer.Exit(1)

    if not no_generate:
        console.print("🔄 Generating dashboard data...")
        generate_script = dashboard_dir / "generate_data.py"
        try:
            result = subprocess.run(
                ["python3", str(generate_script)],
                cwd=dashboard_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                console.print("[yellow]Warning:[/yellow] Data generation failed")
                console.print(f"[dim]{result.stderr}[/dim]")
            else:
                console.print("[green]✓[/green] Dashboard data generated")
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Could not generate data: {e}")

    console.print()
    console.print(Panel(
        f"[bold cyan]🤖 DevBots Dashboard[/bold cyan]\n\n"
        f"[green]Server starting on:[/green] http://localhost:{port}\n\n"
        f"[dim]Available pages:[/dim]\n"
        f"  • Main Dashboard: http://localhost:{port}/\n"
        f"  • Projects:       http://localhost:{port}/projects.html\n"
        f"  • Bots:           http://localhost:{port}/bots.html\n"
        f"  • Activity:       http://localhost:{port}/activity.html\n"
        f"  • Reports:        http://localhost:{port}/reports.html\n\n"
        f"[yellow]Press Ctrl+C to stop the server[/yellow]",
        border_style="cyan",
    ))
    console.print()

    if not no_browser:
        try:
            webbrowser.open(f"http://localhost:{port}")
            console.print("[dim]Opening browser...[/dim]")
        except Exception:
            pass

    server_script = dashboard_dir / "server.py"
    try:
        os.chdir(dashboard_dir)
        subprocess.run(["python3", str(server_script), str(port)])
    except KeyboardInterrupt:
        console.print("\n\n[dim]👋 Dashboard server stopped[/dim]")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def projects(
    registry_path: Annotated[
        Path | None,
        typer.Option("--registry", "-r", help="Path to project registry JSON"),
    ] = None,
    scope: Annotated[
        str | None,
        typer.Option("--scope", "-s", help="Filter by scope: 'team' or 'personal'"),
    ] = None,
):
    """List all registered projects."""
    registry = ProjectRegistry(registry_path)

    if scope:
        try:
            ps = ProjectScope(scope.lower())
        except ValueError:
            console.print(f"[red]Error:[/red] Unknown scope '{scope}'. Use 'team' or 'personal'.")
            raise typer.Exit(1)
        project_list = registry.list_by_scope(ps)
    else:
        project_list = registry.list_projects()

    _show_projects_list(project_list)


@app.command()
def add(
    name: Annotated[str, typer.Argument(help="Project name")],
    path: Annotated[Path, typer.Argument(help="Project path")],
    description: Annotated[str, typer.Option("--desc", "-d", help="Project description")] = "",
    language: Annotated[str, typer.Option("--lang", "-l", help="Primary language")] = "python",
    languages: Annotated[
        list[str] | None,
        typer.Option("--language", help="Project language; repeat or use comma-separated values"),
    ] = None,
    frameworks: Annotated[
        list[str] | None,
        typer.Option("--framework", help="Framework/CMS/runtime; repeat or use comma-separated values"),
    ] = None,
    scope: ScopeOpt = "team",
    gitlab_project_id: GitLabProjectIdOpt = None,
    gitlab_url: GitLabUrlOpt = None,
    gitlab_token: GitLabTokenOpt = None,
    github_repo: GitHubRepoOpt = None,
    site_url: Annotated[str | None, typer.Option("--site-url", help="Public site URL for PageSpeed analysis")] = None,
    audit_urls: Annotated[list[str] | None, typer.Option("--audit-url", help="Additional public URL to audit; repeat for multiple pages")] = None,
    notes_dir: Annotated[str | None, typer.Option("--notes-dir", help="Journal/notes directory (journalbot)")] = None,
    task_file: Annotated[str | None, typer.Option("--task-file", help="Task list file or directory (taskbot)")] = None,
    habit_file: Annotated[str | None, typer.Option("--habit-file", help="Habit log file (habitbot)")] = None,
    registry_path: Annotated[
        Path | None,
        typer.Option("--registry", "-r", help="Path to project registry JSON"),
    ] = None,
):
    """
    Add a project to the registry.

    Examples:\\n
      orchestrator add myapp ~/Projects/myapp\\n
      orchestrator add myapp ~/Projects/myapp --gitlab-id 12345\\n
      orchestrator add journal ~/Notes --scope personal --notes-dir ~/Notes/journal\\n
      orchestrator add tasks ~/Notes --scope personal --task-file ~/Notes/tasks.md\\n
      orchestrator add habits ~/Notes --scope personal --habit-file ~/Notes/habits.csv
    """
    try:
        project_scope = ProjectScope(scope.lower())
    except ValueError:
        console.print(f"[red]Error:[/red] Unknown scope '{scope}'. Use 'team' or 'personal'.")
        raise typer.Exit(1)

    registry = ProjectRegistry(registry_path)

    try:
        registry.add_project(
            name, path,
            description=description,
            language=language,
            languages=_split_multi_values(languages) or [language],
            frameworks=_split_multi_values(frameworks) or None,
            scope=project_scope,
            gitlab_project_id=gitlab_project_id,
            gitlab_url=gitlab_url,
            gitlab_token=gitlab_token,
            github_repo=github_repo,
            site_url=site_url,
            audit_urls=audit_urls,
            notes_dir=notes_dir,
            task_file=task_file,
            habit_file=habit_file,
        )

        scope_label = "[blue]personal[/blue]" if project_scope == ProjectScope.PERSONAL else "[green]team[/green]"
        console.print(f"[green]✓[/green] Added {scope_label} project: [bold]{name}[/bold] → {path}")
        if gitlab_project_id:
            console.print(f"[dim]  GitLab: {gitlab_project_id}" +
                         (f" @ {gitlab_url}" if gitlab_url else "") + "[/dim]")
        if github_repo:
            console.print(f"[dim]  GitHub: {github_repo}[/dim]")
        if site_url:
            console.print(f"[dim]  Site URL: {site_url}[/dim]")
        resolved_languages = _split_multi_values(languages) or [language]
        console.print(f"[dim]  Languages: {', '.join(resolved_languages)}[/dim]")
        if frameworks:
            console.print(f"[dim]  Frameworks: {', '.join(_split_multi_values(frameworks))}[/dim]")
        if audit_urls:
            console.print(f"[dim]  Audit URLs: {', '.join(audit_urls)}[/dim]")
        if notes_dir:
            console.print(f"[dim]  Notes dir: {notes_dir}[/dim]")
        if task_file:
            console.print(f"[dim]  Task file: {task_file}[/dim]")
        if habit_file:
            console.print(f"[dim]  Habit file: {habit_file}[/dim]")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def remove(
    name: Annotated[str, typer.Argument(help="Project name to remove")],
    registry_path: Annotated[
        Path | None,
        typer.Option("--registry", "-r", help="Path to project registry JSON"),
    ] = None,
):
    """Remove a project from the registry."""
    registry = ProjectRegistry(registry_path)
    registry.remove_project(name)
    console.print(f"[green]✓[/green] Removed project: [bold]{name}[/bold]")


def _show_projects(registry: ProjectRegistry) -> None:
    _show_projects_list(registry.list_projects())


def _show_projects_list(project_list: list) -> None:
    if not project_list:
        console.print("[yellow]No projects registered.[/yellow]")
        console.print("[dim]Use '/add' or 'orchestrator add' to register a project[/dim]")
        return

    table = Table(title="Registered Projects", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Scope", style="bold")
    table.add_column("Path")
    table.add_column("Description", style="dim")
    table.add_column("Integration / Data", style="green")

    for proj in project_list:
        parts = []
        if proj.has_gitlab():
            parts.append("GitLab")
        if proj.has_github():
            parts.append("GitHub")
        if proj.site_url:
            parts.append("site")
        if proj.notes_dir:
            parts.append("notes")
        if proj.task_file:
            parts.append("tasks")
        if proj.habit_file:
            parts.append("habits")
        integration_str = ", ".join(parts) if parts else "[dim]—[/dim]"

        scope_display = (
            "[blue]personal[/blue]"
            if proj.scope == ProjectScope.PERSONAL
            else "[green]team[/green]"
        )

        table.add_row(
            proj.name,
            scope_display,
            str(proj.path),
            proj.description or "[dim]—[/dim]",
            integration_str,
        )

    console.print(table)


def _add_project_interactive(registry: ProjectRegistry) -> None:
    name = Prompt.ask("Project name")
    path_str = Prompt.ask("Project path")
    description = Prompt.ask("Description (optional)", default="")
    scope_str = Prompt.ask("Scope", choices=["team", "personal"], default="team")

    try:
        project_scope = ProjectScope(scope_str)
    except ValueError:
        project_scope = ProjectScope.TEAM

    gitlab_id = ""
    github_repo_val = ""
    site_url = ""
    audit_urls_str = ""
    notes_dir = ""
    task_file = ""
    habit_file = ""

    if project_scope == ProjectScope.TEAM:
        console.print("\n[dim]Issue Tracker Integration (optional — enables pmbot)[/dim]")
        gitlab_id = Prompt.ask("GitLab project ID (press Enter to skip)", default="")
        github_repo_val = Prompt.ask("GitHub repo owner/repo (press Enter to skip)", default="")
        site_url = Prompt.ask("Public site URL for PageSpeedBot (press Enter to skip)", default="")
        audit_urls_str = Prompt.ask("Additional audit URLs, comma-separated (press Enter to skip)", default="")
    else:
        console.print("\n[dim]Personal Data Sources (optional)[/dim]")
        notes_dir = Prompt.ask("Notes/journal directory for journalbot (press Enter to skip)", default="")
        task_file = Prompt.ask("Task list file/dir for taskbot (press Enter to skip)", default="")
        habit_file = Prompt.ask("Habit log file for habitbot (press Enter to skip)", default="")

    try:
        registry.add_project(
            name, Path(path_str),
            description=description,
            scope=project_scope,
            gitlab_project_id=gitlab_id if gitlab_id else None,
            github_repo=github_repo_val if github_repo_val else None,
            site_url=site_url if site_url else None,
            audit_urls=[url.strip() for url in audit_urls_str.split(",") if url.strip()] or None,
            notes_dir=notes_dir if notes_dir else None,
            task_file=task_file if task_file else None,
            habit_file=habit_file if habit_file else None,
        )
        console.print(f"[green]✓[/green] Added project: [bold]{name}[/bold]")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


if __name__ == "__main__":
    app()
