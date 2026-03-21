from pathlib import Path

from shared.models import BotResult, BotStatus
from voicebot.analyzer import get_bot_result
from voicebot.language import build_language_candidates, detect_language, normalize_requested_language
from voicebot.transcriber import VoiceTranscript


class FakeTranscriber:
    def __init__(self, transcript: VoiceTranscript):
        self.transcript = transcript

    def transcribe_file(self, audio_file: Path, language: str = "auto") -> VoiceTranscript:
        return self.transcript

    def transcribe_microphone(
        self,
        language: str = "auto",
        timeout: int | None = None,
        phrase_time_limit: int | None = None,
    ) -> VoiceTranscript:
        return self.transcript


def test_language_aliases_prefer_spanish_in_auto_mode():
    assert normalize_requested_language("es") == "es-CO"
    assert build_language_candidates("auto") == ("es-CO", "es-ES", "en-US")


def test_detect_language_marks_spanish_text():
    detection = detect_language("Quiero revisar mis tareas del proyecto")

    assert detection.language == "es"
    assert detection.confidence > 0


def test_voicebot_returns_transcript_without_dispatch():
    transcript = VoiceTranscript(
        text="Quiero revisar mis tareas",
        requested_language="auto",
        locale="es-CO",
        detected_language="es",
        detection_confidence=0.9,
    )

    result = get_bot_result(
        audio_source=Path("sample.wav"),
        dispatch=False,
        transcriber=FakeTranscriber(transcript),
    )

    assert result.status == BotStatus.SUCCESS
    assert result.data["transcript"] == "Quiero revisar mis tareas"
    assert "Voice Command" in result.markdown_report


def test_voicebot_wraps_routed_bot_result(monkeypatch):
    transcript = VoiceTranscript(
        text="get gitbot report for demo",
        requested_language="auto",
        locale="en-US",
        detected_language="en",
        detection_confidence=1.0,
    )

    routed_result = BotResult(
        bot_name="gitbot",
        status=BotStatus.SUCCESS,
        summary="Git summary ready",
        markdown_report="## GitBot Report\n\nEverything looks good.",
    )

    class FakeOutcome:
        def __init__(self):
            self.action_plan = {
                "action": "invoke_bot",
                "bot": "gitbot",
                "project": "demo",
                "explanation": "Run gitbot for demo.",
            }
            self.bot_result = routed_result
            self.projects = []
            self.error = None

    monkeypatch.setattr("voicebot.analyzer.ProjectRegistry", lambda registry_path=None: object())
    monkeypatch.setattr("voicebot.analyzer.process_user_request", lambda user_message, registry: FakeOutcome())

    result = get_bot_result(
        audio_source=Path("sample.wav"),
        dispatch=True,
        transcriber=FakeTranscriber(transcript),
    )

    assert result.status == BotStatus.SUCCESS
    assert result.data["target_bot"] == "gitbot"
    assert "GitBot Report" in result.markdown_report
