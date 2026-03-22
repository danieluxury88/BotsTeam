# DevBots — Project Status

> **Living document.** Update this whenever a feature ships, a gap is closed, or priorities shift.
> Last reviewed: 2026-03-22

---

## What Is Working

### Team Bots ✅

| Bot | CLI | Orchestrator | Dashboard | Notes |
|-----|-----|-------------|-----------|-------|
| GitBot | ✅ | ✅ | ✅ | `--since`/`--until` date filtering |
| QABot | ✅ | ✅ | ✅ | suggest + run + generate + full workflows, including optional coverage reporting |
| PMBot | ✅ | ✅ | ✅ | GitLab & GitHub, analyze + plan + review + create + check workflows |
| Orchestrator | ✅ | — | ✅ | conversational chat, project registry, and `gitbot_qabot` pipeline routing |

### Personal Bots ✅ (code complete, untested end-to-end)

| Bot | CLI | Orchestrator | Dashboard | Data source field |
|-----|-----|-------------|-----------|-------------------|
| JournalBot | ✅ | ✅ | ✅ | `notes_dir` — markdown directory |
| TaskBot | ✅ | ✅ | ✅ | `task_file` — `.md`/`.txt`/todo.txt |
| HabitBot | ✅ | ✅ | ✅ | `habit_file` — CSV or markdown log |
| NoteBot | ✅ | ✅ | ✅ | `data/{project}/notes/` — auto-created, scope-aware, no project field needed; scope `both` |

**Status:** All four bots are implemented and wired up. Register a personal project via the dashboard or CLI to start using them.

### Infrastructure ✅

| Component | Status | Notes |
|-----------|--------|-------|
| `shared/bot_registry.py` | ✅ | Single source of truth; adding a bot touches one file |
| `shared/file_reader.py` | ✅ | Reads markdown dirs, task files, CSV habits; date filtering |
| `shared/data_manager.py` | ✅ | Scope-aware paths; `get_notes_dir()` for per-project notes |
| `ProjectScope` | ✅ | `TEAM` / `PERSONAL` on every project |
| Dual registry | ✅ | `data/projects.json` + `data/personal/projects.json` |
| Dashboard data pipeline | ✅ | `bots.json`, `projects.json`, `index.json`, `dashboard.json`, `calendar.json` |

### Dashboard ✅

| Feature | Status |
|---------|--------|
| Projects page (list, add, edit, delete) | ✅ |
| Scope selector in Add/Edit modal | ✅ |
| Personal bot fields (notes_dir, task_file, habit_file) | ✅ |
| Scope badges (👥 Team / 👤 Personal) on project cards | ✅ |
| Dynamic bot modal (scope-aware, driven by bot_registry) | ✅ |
| Per-project report generation | ✅ |
| Reports page with filters | ✅ |
| Inline markdown report viewer | ✅ |
| Bots page | ✅ |
| Activity feed | ✅ |
| Calendar page (month view, bot report events) | ✅ |
| Dark mode | ✅ |
| Bot registry auto-loaded (`data/bots.json`) | ✅ |
| Notes page (create, view, edit, delete per project) | ✅ |
| Split-pane markdown editor + live preview | ✅ |
| "Improve with AI" note enhancement via NoteBot | ✅ |
| "Analyse Notes" runs NoteBot on all project notes | ✅ |

---

## Known Gaps

### Blocking first personal bot use

- [ ] **No personal project registered.** Run the dashboard and add one via the Projects page (scope = Personal, fill in `notes_dir`/`task_file`/`habit_file`), or via CLI:
  ```bash
  uv run orchestrator add myjournal ~/path/to/notes \
    --scope personal --notes-dir ~/path/to/notes
  ```

### Docs

- [ ] No individual README for JournalBot (`bots/journalbot/README.md`)
- [ ] No individual README for TaskBot (`bots/taskbot/README.md`)
- [ ] No individual README for HabitBot (`bots/habitbot/README.md`)
- [ ] `.env.example` is missing `JOURNALBOT_MODEL`, `TASKBOT_MODEL`, `HABITBOT_MODEL` entries

### Testing

- [ ] No unit tests for personal bots (`journalbot`, `taskbot`, `habitbot`)
- [ ] No tests for `shared/file_reader.py`
- [ ] Dashboard API coverage is still partial; voice and report-improvement paths need broader tests

### Calendar future event sources

- [ ] Issue due/created dates from pmbot (requires pmbot to save `latest_events.json`)
- [ ] Per-commit dates from gitbot (requires gitbot to save `latest_events.json`)
- [ ] Journal entry dates from journalbot (requires date parsing per file)

---

## Roadmap

### Near-term

| Item | Priority | Notes |
|------|----------|-------|
| Register first personal project + run personal bots | High | Validates end-to-end; identifies any runtime issues |
| Personal bot READMEs (x3) | Medium | Consistency with team bots |
| Add personal bot usage examples to main README | Medium | Discoverability |
| Fix `.env.example` for personal bot model overrides | Low | One-line change |

### Medium-term

| Item | Priority | Notes |
|------|----------|-------|
| Slack integration | ✅ Done | `bots/slackbot/` — Socket Mode, DM + @mention, all bots; see `docs/slack-integration.md` |
| Calendar: issue due/created events (pmbot) | Medium | Needs pmbot to export structured event data alongside `.md` |
| Calendar: commit activity events (gitbot) | Low | Needs gitbot to export per-commit dates |
| Multi-bot workflow (gitbot → qabot pipeline) | ✅ Done | Orchestrator supports a first-class `gitbot_qabot` workflow for “recent changes + what to test” requests |
| QABot: test generation | ✅ Done | `uv run qabot generate ...` drafts repo-local test stubs and can write them into the repository |
| GitBot: compare two branches | Low | Diff-based analysis |

### Long-term / Nice-to-have

| Item | Notes |
|------|-------|
| GitHub Actions integration | Gitbot/QABot as CI pipeline steps |
| PMBot: velocity tracking | Sprint-over-sprint comparison |
| PMBot: multi-project comparison | Cross-project issue analytics |
| Unit tests for all bots | pytest coverage across shared + each bot |

---

## How to Add a New Bot

1. Create `bots/newbot/` with its own `pyproject.toml`
2. Implement `analyzer.py` (returns `BotResult`) and `cli.py` (typer)
3. Add one entry to `shared/shared/bot_registry.py`
4. Register in `bots/orchestrator/orchestrator/bot_invoker.py`

The dashboard, report generation, and calendar will pick it up automatically on the next `uv run dashboard generate`.

---

## How to Add a New Calendar Event Source

1. Save structured event data from the bot alongside its markdown report (e.g., `latest_events.json`)
2. Add a new `XxxEventSource` class in `dashboard/generate_data.py`
3. Register it in `DashboardDataGenerator.generate_calendar_json()`
4. Add the event type to `CONFIG.CALENDAR_EVENT_TYPES` in `dashboard/js/config.js`

No other frontend changes needed.
