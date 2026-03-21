"""Speech transcription helpers for VoiceBot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from voicebot.language import build_language_candidates, detect_language, normalize_requested_language

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover - handled at runtime if dependency is missing
    sr = None


class TranscriptionError(RuntimeError):
    """Raised when audio could not be captured or transcribed."""


@dataclass(frozen=True)
class VoiceTranscript:
    """Structured transcript metadata returned by the speech backend."""

    text: str
    requested_language: str
    locale: str
    detected_language: str
    detection_confidence: float
    backend: str = "speechrecognition/google"


class VoiceTranscriber(Protocol):
    """Protocol used by the analyzer so tests can inject fake transcribers."""

    def transcribe_file(self, audio_file: Path, language: str = "auto") -> VoiceTranscript:
        ...

    def transcribe_microphone(
        self,
        language: str = "auto",
        timeout: int | None = None,
        phrase_time_limit: int | None = None,
    ) -> VoiceTranscript:
        ...


@dataclass(frozen=True)
class _TranscriptCandidate:
    transcript: VoiceTranscript
    score: float


class SpeechRecognitionTranscriber:
    """SpeechRecognition-based transcriber with Spanish-first auto mode."""

    def __init__(self) -> None:
        self._recognizer = self._create_recognizer()

    def transcribe_file(self, audio_file: Path, language: str = "auto") -> VoiceTranscript:
        self._require_backend()

        source_path = Path(audio_file)
        if not source_path.exists():
            raise TranscriptionError(f"Audio file not found: {source_path}")

        try:
            with sr.AudioFile(str(source_path)) as source:
                audio = self._recognizer.record(source)
        except Exception as exc:
            raise TranscriptionError(f"Could not read audio file {source_path}: {exc}") from exc

        return self._recognize_audio(audio, language)

    def transcribe_microphone(
        self,
        language: str = "auto",
        timeout: int | None = None,
        phrase_time_limit: int | None = None,
    ) -> VoiceTranscript:
        self._require_backend()

        try:
            with sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit,
                )
        except Exception as exc:
            raise TranscriptionError(
                "Could not access the microphone. Install PyAudio or use `voicebot transcribe <file>` instead."
            ) from exc

        return self._recognize_audio(audio, language)

    def _create_recognizer(self) -> Any:
        self._require_backend()
        recognizer = sr.Recognizer()
        recognizer.pause_threshold = 0.8
        recognizer.dynamic_energy_threshold = True
        return recognizer

    def _recognize_audio(self, audio: Any, language: str) -> VoiceTranscript:
        requested_language = normalize_requested_language(language)
        candidates: list[_TranscriptCandidate] = []

        for locale in build_language_candidates(requested_language):
            try:
                text = self._recognizer.recognize_google(audio, language=locale).strip()
            except sr.UnknownValueError:
                continue
            except sr.RequestError as exc:
                raise TranscriptionError(f"Speech recognition request failed: {exc}") from exc

            if not text:
                continue

            detection = detect_language(text)
            score = self._score_candidate(text, locale, requested_language, detection.language, detection.confidence)
            candidates.append(
                _TranscriptCandidate(
                    transcript=VoiceTranscript(
                        text=text,
                        requested_language=requested_language,
                        locale=locale,
                        detected_language=detection.language,
                        detection_confidence=detection.confidence,
                    ),
                    score=score,
                )
            )

        if not candidates:
            locales = ", ".join(build_language_candidates(requested_language))
            raise TranscriptionError(f"Could not understand the audio in: {locales}")

        return max(candidates, key=lambda item: item.score).transcript

    @staticmethod
    def _score_candidate(
        text: str,
        locale: str,
        requested_language: str,
        detected_language: str,
        detection_confidence: float,
    ) -> float:
        score = min(len(text.split()) * 0.05, 1.0)
        if requested_language != "auto" and locale == requested_language:
            score += 2.0
        if requested_language == "auto" and detected_language != "unknown" and locale.lower().startswith(detected_language):
            score += 1.5 + detection_confidence
        if requested_language == "auto" and locale.lower().startswith("es"):
            score += 0.1
        return score

    @staticmethod
    def _require_backend() -> None:
        if sr is None:
            raise TranscriptionError(
                "SpeechRecognition is not installed. Run `uv sync` to enable voice transcription."
            )
