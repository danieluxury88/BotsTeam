# VoiceBot

VoiceBot adds a spoken-command interface on top of the existing DevBots orchestrator.

It can:

- Transcribe commands from an audio file
- Listen on the default microphone
- Prefer Spanish in `--language auto` mode
- Route the recognized instruction to the orchestrator so users can speak the same commands they would type

## Usage

```bash
# Listen on the microphone and dispatch the command
uv run voicebot listen --language auto

# Transcribe a Spanish recording without executing anything
uv run voicebot transcribe ./comando.wav --language es --no-dispatch

# Transcribe and execute a recorded command
uv run voicebot transcribe ./command.wav --language auto --dispatch
```

## Language Handling

- `--language auto`: tries Spanish first (`es-CO`, then `es-ES`) and falls back to English (`en-US`)
- `--language es`: forces Colombian Spanish locale by default
- `--language en`: forces US English locale by default
- You can also pass an explicit locale like `es-ES` or `en-GB`

## Notes

- File transcription uses `SpeechRecognition`
- Microphone capture uses the same backend and may require `PyAudio` on your machine
- Dispatch mode reuses the orchestrator router, so project registration still happens through `orchestrator add`
