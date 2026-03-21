"""VoiceBot CLI."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown

from shared.config import load_env
from voicebot.analyzer import get_bot_result

load_env()

app = typer.Typer(
    name="voicebot",
    help="🎙️ VoiceBot — speak commands and route them to DevBots",
    add_completion=False,
)
console = Console()


@app.command()
def transcribe(
    audio_file: Annotated[Path, typer.Argument(help="Audio file to transcribe")] | None = None,
    language: Annotated[
        str,
        typer.Option("--language", "-l", help="Speech locale or alias: auto, es, en, es-CO, en-US"),
    ] = "auto",
    dispatch: Annotated[
        bool,
        typer.Option("--dispatch/--no-dispatch", help="Route the transcript through the orchestrator"),
    ] = True,
    registry_path: Annotated[
        Path | None,
        typer.Option("--registry", "-r", help="Path to project registry JSON"),
    ] = None,
):
    """Transcribe an audio file and optionally execute the spoken command."""
    if not audio_file:
        console.print("[red]Error:[/red] Please provide an audio file path.")
        raise typer.Exit(1)

    result = get_bot_result(
        audio_source=audio_file,
        language=language,
        dispatch=dispatch,
        registry_path=registry_path,
    )
    _render_result(result)


@app.command()
def listen(
    language: Annotated[
        str,
        typer.Option("--language", "-l", help="Speech locale or alias: auto, es, en, es-CO, en-US"),
    ] = "auto",
    dispatch: Annotated[
        bool,
        typer.Option("--dispatch/--no-dispatch", help="Route the transcript through the orchestrator"),
    ] = True,
    registry_path: Annotated[
        Path | None,
        typer.Option("--registry", "-r", help="Path to project registry JSON"),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Microphone listen timeout in seconds"),
    ] = 5,
    phrase_time_limit: Annotated[
        int,
        typer.Option("--phrase-time-limit", help="Maximum command length in seconds"),
    ] = 12,
):
    """Listen on the default microphone and optionally execute the spoken command."""
    console.print("[cyan]Listening for a voice command...[/cyan]")
    result = get_bot_result(
        use_microphone=True,
        language=language,
        dispatch=dispatch,
        registry_path=registry_path,
        timeout=timeout,
        phrase_time_limit=phrase_time_limit,
    )
    _render_result(result)


def _render_result(result) -> None:
    status = getattr(result.status, "value", result.status)
    if status == "success":
        console.print(f"[green]✓[/green] {result.summary}")
    elif status == "partial":
        console.print(f"[yellow]⚠[/yellow] {result.summary}")
    else:
        console.print(f"[red]Error:[/red] {result.summary}")
        raise typer.Exit(1)

    console.print()
    console.print(Markdown(result.markdown_report))


if __name__ == "__main__":
    app()
