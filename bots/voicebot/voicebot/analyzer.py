"""VoiceBot analyzer."""

from __future__ import annotations

from pathlib import Path

from orchestrator.registry import ProjectRegistry
from orchestrator.router import format_projects_markdown, process_user_request
from shared.models import BotResult, BotStatus
from voicebot.transcriber import SpeechRecognitionTranscriber, TranscriptionError, VoiceTranscriber


def get_bot_result(
    audio_source: Path | str | None = None,
    *,
    use_microphone: bool = False,
    language: str = "auto",
    dispatch: bool = True,
    registry_path: Path | None = None,
    timeout: int | None = 5,
    phrase_time_limit: int | None = 12,
    transcriber: VoiceTranscriber | None = None,
) -> BotResult:
    """
    Transcribe a spoken command and optionally dispatch it through the orchestrator.

    Args:
        audio_source: Path to an audio file when not using the microphone.
        use_microphone: Capture audio from the default microphone.
        language: Preferred speech locale or `auto`.
        dispatch: When true, route the transcript to the orchestrator.
        registry_path: Optional explicit project registry override.
        timeout: Microphone listen timeout in seconds.
        phrase_time_limit: Maximum phrase length in seconds.
        transcriber: Optional injected transcriber for tests.
    """
    transcriber = transcriber or SpeechRecognitionTranscriber()

    if not use_microphone and not audio_source:
        return BotResult.failure("voicebot", "Provide an audio file or use `voicebot listen`.")

    try:
        if use_microphone:
            transcript = transcriber.transcribe_microphone(
                language=language,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )
        else:
            transcript = transcriber.transcribe_file(Path(audio_source), language=language)
    except TranscriptionError as exc:
        return BotResult.failure("voicebot", str(exc))

    payload = {
        "transcript": transcript.text,
        "requested_language": transcript.requested_language,
        "locale": transcript.locale,
        "detected_language": transcript.detected_language,
        "detection_confidence": transcript.detection_confidence,
        "dispatched": dispatch,
    }
    report_sections = [
        "## Voice Command",
        "",
        f"**Transcript:** {transcript.text}",
        "",
        f"**Speech locale:** `{transcript.locale}`",
        "",
        f"**Detected language:** `{transcript.detected_language}`",
    ]

    if not dispatch:
        return BotResult(
            bot_name="voicebot",
            status=BotStatus.SUCCESS,
            summary=f"Transcribed voice command using {transcript.locale}",
            markdown_report="\n".join(report_sections),
            data=payload,
        )

    registry = ProjectRegistry(registry_path)
    outcome = process_user_request(transcript.text, registry)
    payload["action_plan"] = outcome.action_plan

    explanation = outcome.action_plan.get("explanation")
    if explanation:
        report_sections.extend(["", f"**Router:** {explanation}"])

    if outcome.error:
        report_sections.extend(["", "## Routing Result", "", outcome.error])
        return BotResult(
            bot_name="voicebot",
            status=BotStatus.PARTIAL,
            summary=f"Transcribed voice command but could not complete it: {outcome.error}",
            markdown_report="\n".join(report_sections),
            data=payload,
            errors=[outcome.error],
        )

    if outcome.projects:
        report_sections.extend(["", format_projects_markdown(outcome.projects)])
        return BotResult(
            bot_name="voicebot",
            status=BotStatus.SUCCESS,
            summary=f"Transcribed voice command and listed {len(outcome.projects)} project(s)",
            markdown_report="\n".join(report_sections),
            data=payload,
        )

    if not outcome.bot_result:
        message = "The voice command was transcribed, but no bot action was produced."
        report_sections.extend(["", "## Routing Result", "", message])
        return BotResult(
            bot_name="voicebot",
            status=BotStatus.PARTIAL,
            summary=message,
            markdown_report="\n".join(report_sections),
            data=payload,
            errors=[message],
        )

    nested_result = outcome.bot_result
    payload["target_bot"] = outcome.action_plan.get("bot")
    payload["target_project"] = outcome.action_plan.get("project")
    payload["target_status"] = getattr(nested_result.status, "value", nested_result.status)

    report_sections.extend(
        [
            "",
            "## Routed Command",
            "",
            f"**Bot:** `{payload['target_bot']}`",
            "",
            f"**Project:** `{payload['target_project']}`",
            "",
            "## Bot Report",
            "",
            nested_result.markdown_report or nested_result.summary,
        ]
    )

    target_status = getattr(nested_result.status, "value", nested_result.status)
    voicebot_status = BotStatus.SUCCESS if target_status == "success" else BotStatus.PARTIAL
    summary = (
        f"Transcribed voice command and ran {payload['target_bot']} for {payload['target_project']}"
        if voicebot_status == BotStatus.SUCCESS
        else f"Transcribed voice command but {payload['target_bot']} returned {target_status}"
    )

    return BotResult(
        bot_name="voicebot",
        status=voicebot_status,
        summary=summary,
        markdown_report="\n".join(report_sections),
        data=payload,
        errors=list(nested_result.errors),
    )
