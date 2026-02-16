"""Conversational orchestrator CLI."""

import json
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table

from orchestrator.bot_invoker import invoke_bot
from orchestrator.registry import ProjectRegistry
from shared.config import load_env
from shared.llm import create_client

load_env()

app = typer.Typer(
    name="orchestrator",
    help="🤖 DevBot Orchestrator — Conversational interface to all bots",
    add_completion=False,
)
console = Console()

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
    typer.Option("--github-repo", help="GitHub repository 'owner/repo' (future)")
]

SYSTEM_PROMPT = """\
You are DevBot Orchestrator, an intelligent assistant that helps developers get information about their projects.

You have access to:
1. A project registry - list of known projects with their paths
2. gitbot - analyzes git history and provides summaries
3. qabot - suggests tests based on recent changes
4. pmbot - analyzes issues and generates sprint plans (requires GitLab or GitHub integration)

When the user asks for information, you should:
1. Identify which project they're referring to (match by name)
2. Determine which bot they need:
   - gitbot: for history/changes/commits
   - qabot: for testing/test suggestions
   - pmbot: for issues/sprint planning/backlog (only if project has GitLab or GitHub integration)
3. Return a JSON response with the action to take

Response format:
{
  "action": "invoke_bot" | "list_projects" | "unknown",
  "bot": "gitbot" | "qabot" | "pmbot" | null,
  "project": "project_name" | null,
  "params": {
    "max_commits": 50,
    "pmbot_mode": "analyze" or "plan"
  },
  "explanation": "Brief explanation of what you'll do"
}

Examples:
- "get qabot report for uni.li" → {"action": "invoke_bot", "bot": "qabot", "project": "uni.li", ...}
- "show me gitbot analysis of myproject" → {"action": "invoke_bot", "bot": "gitbot", "project": "myproject", ...}
- "analyze issues for project X" → {"action": "invoke_bot", "bot": "pmbot", "project": "X", "params": {"pmbot_mode": "analyze"}, ...}
- "create sprint plan for project Y" → {"action": "invoke_bot", "bot": "pmbot", "project": "Y", "params": {"pmbot_mode": "plan"}, ...}
- "what projects do you know?" → {"action": "list_projects", ...}

IMPORTANT: pmbot only works if project has GitLab or GitHub integration configured.

Be concise and helpful.
"""


def parse_user_request(user_message: str, available_projects: list[str]) -> dict:
    """Use Claude to parse user request and determine action."""
    client = create_client()

    projects_list = ", ".join(available_projects) if available_projects else "none registered"

    user_prompt = f"""Available projects: {projects_list}

User request: {user_message}

What should I do? Respond with valid JSON only."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = message.content[0].text.strip()

    # Extract JSON from response (handle code blocks)
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {"action": "unknown", "explanation": "Could not parse request"}


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

    Examples:\n
      orchestrator chat\n
      devbot chat

    Then try:\n
      > get qabot report for uni.li\n
      > show me gitbot analysis of myproject\n
      > what projects do you know?
    """
    registry = ProjectRegistry(registry_path)

    console.print()
    console.print(Panel(
        "[bold cyan]DevBot Orchestrator[/bold cyan]\n"
        "[dim]Ask me to get reports from gitbot or qabot for your projects![/dim]\n\n"
        "Commands: /projects, /add, /remove, /exit",
        border_style="cyan",
    ))
    console.print()

    # Show registered projects
    projects = registry.list_projects()
    if projects:
        console.print(f"[green]✓[/green] Registered projects: [bold]{', '.join(p.name for p in projects)}[/bold]")
    else:
        console.print("[yellow]⚠[/yellow] No projects registered. Use [bold]/add[/bold] to register a project.")
    console.print()

    # Chat loop
    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")

            if not user_input.strip():
                continue

            # Handle special commands
            if user_input.startswith("/"):
                command = user_input[1:].lower().strip()

                if command == "exit" or command == "quit":
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

            # Parse request with Claude
            console.print()
            available_projects = [p.name for p in registry.list_projects()]

            try:
                action_plan = parse_user_request(user_input, available_projects)
            except Exception as e:
                console.print(f"[red]Error parsing request:[/red] {e}")
                continue

            # Show what we're doing
            if "explanation" in action_plan:
                console.print(f"[dim]→ {action_plan['explanation']}[/dim]")

            # Execute action
            if action_plan.get("action") == "list_projects":
                _show_projects(registry)

            elif action_plan.get("action") == "invoke_bot":
                bot_name = action_plan.get("bot")
                project_name = action_plan.get("project")
                params = action_plan.get("params", {})

                if not bot_name or not project_name:
                    console.print("[red]Error:[/red] Could not determine bot or project")
                    continue

                # Find project
                project = registry.get_project(project_name)
                if not project:
                    console.print(f"[red]Error:[/red] Project '{project_name}' not found")
                    console.print("[dim]Use /add to register it first[/dim]")
                    continue

                # Invoke bot
                console.print(f"[cyan]Running {bot_name} on {project.name}...[/cyan]")
                console.print()

                # Handle pmbot differently (requires GitLab or GitHub integration)
                if bot_name == "pmbot":
                    pmbot_mode = params.get("pmbot_mode", "analyze")

                    if not project.has_gitlab() and not project.has_github():
                        console.print(
                            "[yellow]⚠[/yellow] pmbot requires GitLab or GitHub integration\n"
                            f"[dim]Project '{project.name}' has no issue tracker configured.[/dim]\n\n"
                            "To enable pmbot:\n"
                            f"  [bold]orchestrator add {project.name} {project.path} "
                            f"--gitlab-id YOUR_PROJECT_ID[/bold]\n"
                            f"  [bold]orchestrator add {project.name} {project.path} "
                            f"--github-repo owner/repo[/bold]\n"
                        )
                        continue

                    result = invoke_bot(bot_name, project=project, pmbot_mode=pmbot_mode)
                else:
                    # gitbot/qabot
                    max_commits = params.get("max_commits", 50)
                    result = invoke_bot(bot_name, project=project, max_commits=max_commits)

                if result.status == "success":
                    console.print(Rule(f"[dim]{bot_name.upper()} Report[/dim]"))
                    console.print(Markdown(result.markdown_report))
                else:
                    console.print(f"[red]Error:[/red] {result.summary}")

            else:
                console.print("[yellow]⚠[/yellow] Sorry, I couldn't understand that request.")
                console.print("[dim]Try: 'get qabot report for myproject' or 'show gitbot analysis of myproject'[/dim]")

            console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break


@app.command()
def dashboard(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to serve dashboard on")] = 8080,
    no_generate: Annotated[bool, typer.Option("--no-generate", help="Skip data generation")] = False,
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Don't open browser")] = False,
):
    """
    Launch the DevBots Dashboard web interface.
    
    Generates data and starts a local web server to view projects, bots, and reports.
    
    Examples:\n
      orchestrator dashboard\n
      orchestrator dashboard --port 3000\n
      orchestrator dashboard --no-generate  # Use existing data
    """
    # Find dashboard directory
    repo_root = Path(__file__).parent.parent.parent.parent
    dashboard_dir = repo_root / "dashboard"
    
    if not dashboard_dir.exists():
        console.print("[red]Error:[/red] Dashboard directory not found")
        console.print(f"[dim]Expected: {dashboard_dir}[/dim]")
        raise typer.Exit(1)
    
    # Generate data
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
                console.print(f"[yellow]Warning:[/yellow] Data generation failed")
                console.print(f"[dim]{result.stderr}[/dim]")
            else:
                console.print("[green]✓[/green] Dashboard data generated")
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Could not generate data: {e}")
    
    # Print instructions
    console.print()
    console.print(Panel(
        f"[bold cyan]🤖 DevBots Dashboard[/bold cyan]\n\n"
        f"[green]Server starting on:[/green] http://localhost:{port}\n\n"
        f"[dim]Available pages:[/dim]\n"
        f"  • Main Dashboard: http://localhost:{port}/\n"
        f"  • Projects:       http://localhost:{port}/projects.html\n"
        f"  • Bots:           http://localhost:{port}/bots.html\n"
        f"  • Activity:       http://localhost:{port}/activity.html\n\n"
        f"[yellow]Press Ctrl+C to stop the server[/yellow]",
        border_style="cyan",
    ))
    console.print()
    
    # Open browser
    if not no_browser:
        try:
            webbrowser.open(f"http://localhost:{port}")
            console.print("[dim]Opening browser...[/dim]")
        except Exception:
            pass
    
    # Start server
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
):
    """List all registered projects."""
    registry = ProjectRegistry(registry_path)
    _show_projects(registry)


@app.command()
def add(
    name: Annotated[str, typer.Argument(help="Project name")],
    path: Annotated[Path, typer.Argument(help="Project path")],
    description: Annotated[str, typer.Option("--desc", "-d", help="Project description")] = "",
    language: Annotated[str, typer.Option("--lang", "-l", help="Primary language")] = "python",
    gitlab_project_id: GitLabProjectIdOpt = None,
    gitlab_url: GitLabUrlOpt = None,
    gitlab_token: GitLabTokenOpt = None,
    github_repo: GitHubRepoOpt = None,
    registry_path: Annotated[
        Path | None,
        typer.Option("--registry", "-r", help="Path to project registry JSON"),
    ] = None,
):
    """
    Add a project to the registry.

    Examples:\n
      # Basic project (gitbot/qabot only)
      orchestrator add uni.li ~/Projects/uni.li

      # With GitLab integration (enables pmbot)
      orchestrator add myapp ~/Projects/myapp --gitlab-id 12345

      # With per-project token
      orchestrator add myapp ~/Projects/myapp --gitlab-id 12345 --gitlab-token glpat-xxxxx
    """
    registry = ProjectRegistry(registry_path)

    try:
        registry.add_project(
            name, path, description=description, language=language,
            gitlab_project_id=gitlab_project_id,
            gitlab_url=gitlab_url,
            gitlab_token=gitlab_token,
            github_repo=github_repo,
        )

        console.print(f"[green]✓[/green] Added project: [bold]{name}[/bold] → {path}")
        if gitlab_project_id:
            console.print(f"[dim]  GitLab: {gitlab_project_id}" +
                         (f" @ {gitlab_url}" if gitlab_url else "") + "[/dim]")
        if github_repo:
            console.print(f"[dim]  GitHub: {github_repo}[/dim]")

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


def _show_projects(registry: ProjectRegistry):
    """Display registered projects in a table."""
    projects = registry.list_projects()

    if not projects:
        console.print("[yellow]No projects registered.[/yellow]")
        console.print("[dim]Use '/add' or 'orchestrator add' to register a project[/dim]")
        return

    table = Table(title="Registered Projects", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Path")
    table.add_column("Description", style="dim")
    table.add_column("Integration", style="green")

    for proj in projects:
        integrations = []
        if proj.has_gitlab():
            integrations.append("GitLab")
        if proj.has_github():
            integrations.append("GitHub")
        integration_str = ", ".join(integrations) if integrations else "[dim]—[/dim]"

        table.add_row(
            proj.name,
            str(proj.path),
            proj.description or "[dim]—[/dim]",
            integration_str,
        )

    console.print(table)


def _add_project_interactive(registry: ProjectRegistry):
    """Interactively add a project."""
    name = Prompt.ask("Project name")
    path_str = Prompt.ask("Project path")
    description = Prompt.ask("Description (optional)", default="")

    console.print("\n[dim]Issue Tracker Integration (optional - enables pmbot)[/dim]")
    gitlab_id = Prompt.ask("GitLab project ID (press Enter to skip)", default="")
    github_repo = Prompt.ask("GitHub repo owner/repo (press Enter to skip)", default="")

    try:
        registry.add_project(
            name, Path(path_str), description=description,
            gitlab_project_id=gitlab_id if gitlab_id else None,
            github_repo=github_repo if github_repo else None,
        )
        console.print(f"[green]✓[/green] Added project: [bold]{name}[/bold]")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


if __name__ == "__main__":
    app()
