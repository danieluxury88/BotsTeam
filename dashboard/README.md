# DevBots Dashboard

The dashboard is the browser and PWA surface for DevBots. It combines static HTML/CSS/JS with a lightweight Python API layer for project management, report generation, note improvement, and voice-driven orchestrator requests.

## Features

- Projects, bots, activity, reports, notes, and report export/improvement flows.
- Home-page Voice Bridge with browser speech recognition, Spanish-first language options, and manual transcript fallback.
- Background voice command jobs so long bot runs keep reporting progress instead of blocking one request.
- Replaceable reply speech service with browser TTS, natural-voice ranking, speed control, and optional autoplay.
- PWA install support for desktop and mobile browsers.
- No frontend build step.

## Quick Start

From the repository root:

```bash
uv sync
uv run dashboard
```

Useful variants:

```bash
uv run dashboard --port 3000
uv run dashboard generate
uv run orchestrator dashboard
```

The dashboard is available at `http://localhost:8080` by default.

## Directory Structure

```text
dashboard/
├── index.html              # Home dashboard + voice bridge
├── server.py               # Static server + REST API routing
├── api.py                  # API handlers, report generation, voice jobs
├── generate_data.py        # JSON generation for dashboard/data/
├── css/                    # Stylesheets
├── js/                     # JavaScript modules
│   ├── api.js              # Fetch helpers and voice job polling
│   ├── dashboard.js        # Page bootstrap
│   ├── voice.js            # Voice input + routed result UI
│   └── speech-output.js    # Replaceable reply speech service
├── data/                   # Generated JSON files
└── tests/                  # Dashboard API tests
```

## Voice Workflow

The voice console on the home page is intended for the browser and PWA experience:

1. Tap `Start Listening` and speak in `Español (CO)`, `Español (ES)`, or `English (US)`.
2. Review or edit the transcript.
3. Press `Send Command`.
4. The browser posts the transcript to `/api/voice-command`.
5. The server creates a background job and the UI polls until the routed bot finishes.
6. The result appears in text and can optionally be read aloud by the reply speech service.

Notes:

- Voice recognition depends on the browser Web Speech API. If it is unavailable, you can still type a transcript manually.
- Reply speech uses the browser `speechSynthesis` API by default.
- Service workers cannot capture microphone input in the background, so this is a foreground tap-to-talk flow.
- Long-running commands are now processed as background jobs rather than one blocking request.

## API Notes

Relevant voice endpoints:

- `POST /api/voice-command` starts a background voice command job.
- `GET /api/voice-command/{job_id}` returns the current job state and final routed result.

The dashboard server uses `ThreadingTCPServer` so polling continues while a bot run is still in flight.

## Development

Common checks:

```bash
python3 -m py_compile dashboard/api.py dashboard/server.py
node --check dashboard/js/api.js
node --check dashboard/js/voice.js
node --check dashboard/js/speech-output.js
pytest dashboard/tests/test_api.py
```

## Documentation

Related docs:

- `docs/DASHBOARD.md` - Dashboard architecture and API overview
- `dashboard/PWA.md` - PWA setup and installation notes
- `docs/dashboard-implementation.md` - Original implementation guide

## Troubleshooting

- If voice status never updates, restart the dashboard server so the threaded API handler is active.
- If browser speech recognition is unavailable, test with manual transcript entry first.
- If reply speech fails, hard refresh the page so the latest `speech-output.js` is loaded and reselect a voice.
- If the dashboard is empty, run `uv run dashboard generate` and reload.
