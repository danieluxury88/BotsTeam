"""DevBots Dashboard CLI — standalone entry point."""

import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="dashboard",
    help="DevBots Dashboard — web interface for projects and reports",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()


def _find_dashboard_dir() -> Path:
    """Locate the dashboard/ directory relative to the repo root."""
    # Walk up from this file to find the repo root containing dashboard/
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "dashboard"
        if candidate.is_dir() and (candidate / "index.html").exists():
            return candidate
    # Fallback: assume standard layout (bots/dashboard/dashboard_cli/cli.py -> repo root)
    repo_root = Path(__file__).parent.parent.parent.parent
    return repo_root / "dashboard"


@app.callback()
def main(
    ctx: typer.Context,
    port: Annotated[int, typer.Option("--port", "-p", help="Port to serve dashboard on")] = 8080,
    no_generate: Annotated[bool, typer.Option("--no-generate", help="Skip data generation")] = False,
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Don't open browser")] = False,
) -> None:
    """
    Launch the DevBots Dashboard web interface.

    Generates data and starts a local web server to view projects, bots, and reports.

    Examples:\n
      dashboard\n
      dashboard --port 3000\n
      dashboard --no-generate
    """
    # If a subcommand was invoked, skip the default behavior
    if ctx.invoked_subcommand is not None:
        return

    dashboard_dir = _find_dashboard_dir()

    if not dashboard_dir.exists():
        console.print("[red]Error:[/red] Dashboard directory not found")
        console.print(f"[dim]Expected: {dashboard_dir}[/dim]")
        raise typer.Exit(1)

    _generate_data(dashboard_dir, skip=no_generate)
    _serve(dashboard_dir, port=port, open_browser=not no_browser)


@app.command()
def generate() -> None:
    """Regenerate dashboard JSON data without starting the server."""
    dashboard_dir = _find_dashboard_dir()

    if not dashboard_dir.exists():
        console.print("[red]Error:[/red] Dashboard directory not found")
        raise typer.Exit(1)

    _generate_data(dashboard_dir, skip=False)


def _generate_data(dashboard_dir: Path, *, skip: bool) -> None:
    """Run generate_data.py to produce JSON files."""
    if skip:
        return

    console.print("Generating dashboard data...")
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


def _serve(dashboard_dir: Path, *, port: int, open_browser: bool) -> None:
    """Start the dashboard HTTP server."""
    console.print()
    console.print(Panel(
        f"[bold cyan]DevBots Dashboard[/bold cyan]\n\n"
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

    if open_browser:
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
        console.print("\n\n[dim]Dashboard server stopped[/dim]")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1)
