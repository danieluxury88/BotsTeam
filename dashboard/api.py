"""REST API handlers for project CRUD operations."""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Ensure orchestrator and shared packages are importable
REPO_ROOT = Path(__file__).resolve().parent.parent
BOT_PACKAGES = [path for path in (REPO_ROOT / "bots").iterdir() if path.is_dir()]
SHARED_PKG = REPO_ROOT / "shared"
for _pkg in [*BOT_PACKAGES, SHARED_PKG]:
    if str(_pkg) not in sys.path:
        sys.path.insert(0, str(_pkg))

from orchestrator.registry import ProjectRegistry  # noqa: E402
from orchestrator.router import process_user_request  # noqa: E402
from generate_data import DashboardDataGenerator  # noqa: E402
from shared.bot_registry import BOTS as _BOT_REGISTRY, runnable_bots as _runnable_bots  # noqa: E402
from shared.config import load_env  # noqa: E402
from shared.data_manager import get_data_root, get_notes_dir, get_reports_dir  # noqa: E402
from shared.models import ProjectScope  # noqa: E402
from shared.report_export import export_report_file  # noqa: E402

load_env()

NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')
AI_BOTS = {"gitbot", "qabot", "pmbot", "journalbot", "taskbot", "habitbot", "notebot", "orchestrator"}


def _parse_audit_urls(value):
    if value is None:
        return None
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or None
    text = str(value).strip()
    if not text:
        return None
    cleaned = [line.strip() for line in text.splitlines() if line.strip()]
    return cleaned or None


def _registry():
    return ProjectRegistry()


def _regenerate_dashboard():
    """Regenerate static JSON files after a mutation."""
    gen = DashboardDataGenerator()
    gen.run()


def _validate_name(name):
    if not name or not NAME_PATTERN.match(name):
        return "Name must start with a letter/digit and contain only letters, digits, hyphens, underscores."
    return None


def _project_to_dict(project):
    """Convert a Project to a JSON-safe dict, excluding tokens."""
    d = project.to_dict()
    d.pop("gitlab_token", None)
    d.pop("github_token", None)
    return d


def _artifact_url(project, bot_name, file_path):
    """Convert a saved report artifact path into a dashboard-served URL."""
    if not file_path:
        return None

    filename = Path(file_path).name
    if project.scope == ProjectScope.PERSONAL:
        return f"reports/personal/{project.name}/{bot_name}/{filename}"
    return f"reports/{project.name}/{bot_name}/{filename}"


def _artifact_url_from_parts(scope, project_name, bot_name, file_path):
    if not file_path:
        return None

    filename = Path(file_path).name
    if scope == ProjectScope.PERSONAL:
        return f"reports/personal/{project_name}/{bot_name}/{filename}"
    return f"reports/{project_name}/{bot_name}/{filename}"


def _load_reportbot_improver():
    """Import and return ReportBot's improve function lazily."""
    reportbot_pkg = REPO_ROOT / "bots" / "reportbot"
    if str(reportbot_pkg) not in sys.path:
        sys.path.insert(0, str(reportbot_pkg))
    from reportbot.analyzer import improve_report  # noqa: E402

    return improve_report


def _parse_report_reference(report_path: str):
    """Resolve a dashboard report URL to a concrete markdown report file."""
    normalized = (report_path or "").strip().lstrip("/")
    parts = normalized.split("/")

    if len(parts) == 4 and parts[0] == "reports":
        _, project_name, bot_name, filename = parts
        scope = ProjectScope.TEAM
    elif len(parts) == 5 and parts[0] == "reports" and parts[1] == "personal":
        _, _, project_name, bot_name, filename = parts
        scope = ProjectScope.PERSONAL
    else:
        return None, {"error": "Invalid report path."}, 400

    if not filename.endswith(".md"):
        return None, {"error": "Only markdown reports can be exported."}, 400

    reports_root = get_data_root() / "personal" if scope == ProjectScope.PERSONAL else get_data_root()
    base_dir = reports_root / project_name / "reports" / bot_name
    source = base_dir / filename
    try:
        source.resolve().relative_to(base_dir.resolve())
    except ValueError:
        return None, {"error": "Invalid report path."}, 400
    if not source.exists():
        return None, {"error": f"Report not found: {report_path}"}, 404

    return {
        "scope": scope,
        "project_name": project_name,
        "bot_name": bot_name,
        "filename": filename,
        "source": source,
    }, None, None


def _metadata_for_existing_report(project_name: str, bot_name: str, source: Path) -> dict:
    bot_meta = _BOT_REGISTRY.get(bot_name)
    bot_label = bot_meta.name if bot_meta else bot_name
    generated_at = datetime.fromtimestamp(source.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    metadata = {
        "title": f"{bot_label} Report",
        "subtitle": "Exported from an existing DevBots markdown report",
        "project_name": project_name,
        "generated_at": generated_at,
        "author": bot_label,
        "kicker": "Technical Audit Report" if bot_name == "pagespeedbot" else "DevBots Report Export",
        "document_type": "SEO & Performance Audit" if bot_name == "pagespeedbot" else "Technical Review",
        "primary_scope": "Search, Technical SEO, and Core Web Vitals" if bot_name == "pagespeedbot" else "Bot Report Export",
        "confidentiality": "Client Confidential" if bot_name == "pagespeedbot" else "Internal Use",
        "footer_text": (
            f"Prepared by ProtonSystems using DevBots {bot_label} export"
            if bot_name == "pagespeedbot"
            else f"Generated by DevBots from an existing {bot_label} report"
        ),
    }
    return metadata


def list_projects():
    registry = _registry()
    projects = registry.list_projects()
    return {"projects": [_project_to_dict(p) for p in projects]}


def get_project(name):
    registry = _registry()
    if name not in registry.projects:
        return None
    return _project_to_dict(registry.projects[name])


def _parse_scope(data):
    try:
        return ProjectScope(data.get("scope", "team"))
    except ValueError:
        return ProjectScope.TEAM


def _resolve_path(path_str, scope):
    """Resolve and validate a project path. Personal projects may omit path."""
    path_str = (path_str or "").strip()
    if not path_str:
        if scope == ProjectScope.PERSONAL:
            return Path.home(), None  # default to home dir
        return None, "Path is required for team projects."
    path_obj = Path(path_str).expanduser()
    if not path_obj.exists():
        return None, f"Path does not exist: {path_str}"
    return path_obj, None


def create_project(data):
    name = data.get("name", "").strip()
    err = _validate_name(name)
    if err:
        return {"error": err}, 400

    scope = _parse_scope(data)
    path_obj, err = _resolve_path(data.get("path", ""), scope)
    if err:
        return {"error": err}, 400

    registry = _registry()
    if name in registry.projects:
        return {"error": f"Project '{name}' already exists."}, 409

    registry.add_project(
        name=name,
        path=str(path_obj),
        description=data.get("description", ""),
        language=data.get("language", "python"),
        scope=scope,
        gitlab_project_id=data.get("gitlab_project_id") or None,
        gitlab_url=data.get("gitlab_url") or None,
        github_repo=data.get("github_repo") or None,
        site_url=data.get("site_url") or None,
        audit_urls=_parse_audit_urls(data.get("audit_urls")),
        notes_dir=data.get("notes_dir") or None,
        task_file=data.get("task_file") or None,
        habit_file=data.get("habit_file") or None,
    )

    _regenerate_dashboard()
    return _project_to_dict(registry.projects[name]), 201


def update_project(name, data):
    registry = _registry()
    if name not in registry.projects:
        return {"error": f"Project '{name}' not found."}, 404

    project = registry.projects[name]

    # Update allowed fields
    if "path" in data and data["path"]:
        new_path, err = _resolve_path(data["path"], project.scope)
        if err:
            return {"error": err}, 400
        project.path = new_path

    if "description" in data:
        project.description = data["description"]
    if "language" in data:
        project.language = data["language"]
    if "gitlab_project_id" in data:
        project.gitlab_project_id = data["gitlab_project_id"] or None
    if "gitlab_url" in data:
        project.gitlab_url = data["gitlab_url"] or None
    if "github_repo" in data:
        project.github_repo = data["github_repo"] or None
    if "site_url" in data:
        project.site_url = data["site_url"] or None
    if "audit_urls" in data:
        project.audit_urls = _parse_audit_urls(data["audit_urls"])
    if "notes_dir" in data:
        project.notes_dir = data["notes_dir"] or None
    if "task_file" in data:
        project.task_file = data["task_file"] or None
    if "habit_file" in data:
        project.habit_file = data["habit_file"] or None

    registry._save()
    _regenerate_dashboard()
    return _project_to_dict(project), 200


def delete_project(name):
    registry = _registry()
    if name not in registry.projects:
        return {"error": f"Project '{name}' not found."}, 404

    registry.remove_project(name)
    _regenerate_dashboard()
    return {"deleted": name}, 200


def generate_reports(name, data):
    """Run selected bots for a project and return results."""
    from orchestrator.bot_invoker import invoke_bot

    registry = _registry()
    if name not in registry.projects:
        return {"error": f"Project '{name}' not found."}, 404

    project = registry.projects[name]

    bots = data.get("bots", [])
    if not bots:
        return {"error": "No bots selected."}, 400

    valid_bots = set(_runnable_bots())
    invalid = [b for b in bots if b not in valid_bots]
    if invalid:
        return {"error": f"Unknown bots: {', '.join(invalid)}"}, 400

    if any(bot in AI_BOTS for bot in bots) and not os.environ.get("ANTHROPIC_API_KEY"):
        return {
            "error": "ANTHROPIC_API_KEY is not set. Add it to your .env file and restart the server."
        }, 400

    since = data.get("since") or None
    until = data.get("until") or None
    pmbot_mode = data.get("pmbot_mode", "analyze")

    results = {}
    completed = 0
    failed = 0

    for bot_name in bots:
        try:
            kwargs = {"bot_name": bot_name, "project": project}
            if bot_name == "gitbot":
                kwargs["since"] = since
                kwargs["until"] = until
            elif bot_name == "pmbot":
                kwargs["pmbot_mode"] = pmbot_mode

            result = invoke_bot(**kwargs)
            status_str = str(result.status.value) if hasattr(result.status, 'value') else str(result.status)
            result_entry = {
                "status": status_str,
                "summary": result.summary,
            }
            report_saved = result.data.get("report_saved", {}) if isinstance(result.data, dict) else {}
            export_saved = result.data.get("export_saved", {}) if isinstance(result.data, dict) else {}

            artifacts = {}
            markdown_path = _artifact_url(project, bot_name, report_saved.get("latest"))
            if markdown_path:
                artifacts["md"] = markdown_path
            html_path = _artifact_url(project, bot_name, export_saved.get("html", {}).get("latest"))
            if html_path:
                artifacts["html"] = html_path
            pdf_path = _artifact_url(project, bot_name, export_saved.get("pdf", {}).get("latest"))
            if pdf_path:
                artifacts["pdf"] = pdf_path
            if artifacts:
                result_entry["artifacts"] = artifacts

            results[bot_name] = result_entry
            if status_str in ("error", "failed"):
                failed += 1
            else:
                completed += 1
        except Exception as e:
            results[bot_name] = {"status": "error", "summary": str(e)}
            failed += 1

    _regenerate_dashboard()
    return {"results": results, "completed": completed, "failed": failed}, 200


def execute_voice_command(data):
    """Route a transcript from the dashboard voice UI through the orchestrator."""
    transcript = str(data.get("transcript", "")).strip()
    locale = str(data.get("locale", "es-CO")).strip() or "es-CO"
    source = str(data.get("source", "dashboard")).strip() or "dashboard"

    if not transcript:
        return {"error": "Transcript is required."}, 400

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {
            "error": "ANTHROPIC_API_KEY is not set. Add it to your .env file and restart the server."
        }, 400

    registry = _registry()
    outcome = process_user_request(transcript, registry)
    action_plan = outcome.action_plan

    response = {
        "transcript": transcript,
        "locale": locale,
        "source": source,
        "action_plan": action_plan,
        "explanation": action_plan.get("explanation"),
    }

    if outcome.projects:
        response["kind"] = "project_list"
        response["projects"] = [_project_to_dict(project) for project in outcome.projects]
        response["count"] = len(outcome.projects)
        return response, 200

    if outcome.error:
        response["kind"] = "error"
        response["error"] = outcome.error
        return response, 200

    if not outcome.bot_result:
        response["kind"] = "error"
        response["error"] = "The command was parsed, but no bot action was produced."
        return response, 200

    bot_result = outcome.bot_result
    bot_name = action_plan.get("bot")
    project_name = action_plan.get("project")
    status_str = bot_result.status.value if hasattr(bot_result.status, "value") else str(bot_result.status)

    response["kind"] = "bot_result"
    response["result"] = {
        "bot_name": bot_name,
        "project_name": project_name,
        "status": status_str,
        "summary": bot_result.summary,
        "markdown_report": bot_result.markdown_report,
        "errors": list(bot_result.errors),
    }

    if project_name and bot_name and isinstance(bot_result.data, dict):
        project = registry.get_project(project_name)
        if project:
            report_saved = bot_result.data.get("report_saved", {})
            export_saved = bot_result.data.get("export_saved", {})
            artifacts = {}

            markdown_path = _artifact_url(project, bot_name, report_saved.get("latest"))
            if markdown_path:
                artifacts["md"] = markdown_path

            html_path = _artifact_url(project, bot_name, export_saved.get("html", {}).get("latest"))
            if html_path:
                artifacts["html"] = html_path

            pdf_path = _artifact_url(project, bot_name, export_saved.get("pdf", {}).get("latest"))
            if pdf_path:
                artifacts["pdf"] = pdf_path

            if artifacts:
                response["result"]["artifacts"] = artifacts

    _regenerate_dashboard()
    return response, 200


def export_existing_report(data):
    """Generate HTML/PDF artifacts for an already saved markdown report."""
    report_path = data.get("path", "")
    resolved, error_body, error_status = _parse_report_reference(report_path)
    if error_body:
        return error_body, error_status

    assert resolved is not None
    source = resolved["source"]
    bot_name = resolved["bot_name"]
    project_name = resolved["project_name"]
    scope = resolved["scope"]

    metadata = _metadata_for_existing_report(project_name, bot_name, source)
    template_name = "protonsystems_audit" if bot_name == "pagespeedbot" else "default"
    branding_name = "protonsystems" if bot_name == "pagespeedbot" else "default"

    export_result = export_report_file(
        source,
        template_name=template_name,
        branding_name=branding_name,
        metadata=metadata,
    )

    _regenerate_dashboard()

    return {
        "artifacts": {
            "md": _artifact_url_from_parts(scope, project_name, bot_name, source),
            "html": _artifact_url_from_parts(scope, project_name, bot_name, export_result.html_paths[0] if export_result.html_paths else None),
            "pdf": _artifact_url_from_parts(scope, project_name, bot_name, export_result.pdf_paths[0] if export_result.pdf_paths else None),
        },
        "errors": export_result.errors,
    }, 200


def preview_report_improvement(data):
    """Generate an improved report draft with ReportBot without saving it."""
    report_path = data.get("path", "")
    resolved, error_body, error_status = _parse_report_reference(report_path)
    if error_body:
        return error_body, error_status

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY is not set."}, 400

    assert resolved is not None
    source = resolved["source"]

    try:
        improve_report = _load_reportbot_improver()
        content = source.read_text(encoding="utf-8")
        improved = improve_report(content, title=source.name)
    except Exception as exc:
        return {"error": f"Improve failed: {exc}"}, 500

    return {
        "improved": improved,
        "source": {
            "path": report_path,
            "filename": source.name,
        },
    }, 200


def _build_improved_report_filename(source_bot: str, source: Path) -> str:
    """Build a timestamped filename for an improved sibling report."""
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    stem = source.stem
    marker = "-reportbot-improved"
    if marker in stem:
        stem = stem.split(marker, 1)[0]
    if source_bot != "reportbot" and not stem.startswith(f"{source_bot}-"):
        stem = f"{source_bot}-{stem}"
    return f"{stem}-reportbot-improved-{timestamp}.md"


def save_report_improvement(data):
    """Persist an improved report draft as a new markdown file."""
    report_path = data.get("path", "")
    improved = data.get("improved", "")
    if not isinstance(improved, str) or not improved.strip():
        return {"error": "Improved report content is required."}, 400

    resolved, error_body, error_status = _parse_report_reference(report_path)
    if error_body:
        return error_body, error_status

    assert resolved is not None
    source = resolved["source"]
    target_dir = get_reports_dir(
        resolved["project_name"],
        "reportbot",
        resolved["scope"],
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / _build_improved_report_filename(
        resolved["bot_name"],
        source,
    )

    try:
        target.write_text(improved, encoding="utf-8")
    except Exception as exc:
        return {"error": f"Could not save improved report: {exc}"}, 500

    _regenerate_dashboard()

    return {
        "artifacts": {
            "md": _artifact_url_from_parts(
                resolved["scope"],
                resolved["project_name"],
                "reportbot",
                target,
            ),
        },
        "saved": {
            "filename": target.name,
        },
    }, 201


# ── Notes CRUD ────────────────────────────────────────────────────────────────

_NOTE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9 _-]*\.md$')


def _validate_note_filename(filename: str) -> str | None:
    """Return an error string if the filename is invalid, else None."""
    if not filename:
        return "Filename is required."
    if "/" in filename or "\\" in filename or ".." in filename:
        return "Filename must not contain path separators."
    if not _NOTE_NAME_PATTERN.match(filename):
        return "Filename must end in .md and contain only letters, digits, spaces, hyphens, or underscores."
    return None


def _resolve_note_path(project_name: str, filename: str):
    """
    Resolve (notes_dir, note_path, error) for a project note.
    Returns (notes_dir, note_path, None) on success or (None, None, error_string).
    """
    registry = _registry()
    if project_name not in registry.projects:
        return None, None, f"Project '{project_name}' not found."

    project = registry.projects[project_name]
    notes_dir = get_notes_dir(project_name, project.scope)
    notes_dir.mkdir(parents=True, exist_ok=True)

    err = _validate_note_filename(filename)
    if err:
        return None, None, err

    note_path = notes_dir / filename
    # Security: ensure resolved path is still inside notes_dir
    try:
        note_path.resolve().relative_to(notes_dir.resolve())
    except ValueError:
        return None, None, "Invalid file path."

    return notes_dir, note_path, None


def _note_to_dict(note_path: Path) -> dict:
    stat = note_path.stat()
    return {
        "filename": note_path.name,
        "modified": stat.st_mtime,
        "size_bytes": stat.st_size,
    }


def list_notes(project_name: str) -> dict:
    registry = _registry()
    if project_name not in registry.projects:
        return {"error": f"Project '{project_name}' not found."}, 404

    project = registry.projects[project_name]
    notes_dir = get_notes_dir(project_name, project.scope)
    notes_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(notes_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    return {"notes": [_note_to_dict(f) for f in files]}


def get_note(project_name: str, filename: str) -> dict:
    notes_dir, note_path, err = _resolve_note_path(project_name, filename)
    if err:
        return {"error": err}, 404

    if not note_path.exists():
        return {"error": f"Note '{filename}' not found."}, 404

    return {
        "filename": filename,
        "content": note_path.read_text(encoding="utf-8"),
        "modified": note_path.stat().st_mtime,
    }


def create_note(project_name: str, data: dict) -> tuple:
    name = (data.get("name") or "").strip()
    if not name:
        return {"error": "Note name is required."}, 400

    # Ensure .md extension
    if not name.endswith(".md"):
        name = name + ".md"

    notes_dir, note_path, err = _resolve_note_path(project_name, name)
    if err:
        return {"error": err}, 400

    if note_path.exists():
        return {"error": f"Note '{name}' already exists."}, 409

    content = data.get("content", "")
    note_path.write_text(content, encoding="utf-8")
    _regenerate_dashboard()
    return {**_note_to_dict(note_path), "content": content}, 201


def update_note(project_name: str, filename: str, data: dict) -> tuple:
    notes_dir, note_path, err = _resolve_note_path(project_name, filename)
    if err:
        return {"error": err}, 400

    if not note_path.exists():
        return {"error": f"Note '{filename}' not found."}, 404

    content = data.get("content", "")
    note_path.write_text(content, encoding="utf-8")
    _regenerate_dashboard()
    return {**_note_to_dict(note_path), "content": content}, 200


def delete_note(project_name: str, filename: str) -> tuple:
    notes_dir, note_path, err = _resolve_note_path(project_name, filename)
    if err:
        return {"error": err}, 400

    if not note_path.exists():
        return {"error": f"Note '{filename}' not found."}, 404

    note_path.unlink()
    _regenerate_dashboard()
    return {"deleted": filename}, 200


def improve_note_api(project_name: str, filename: str) -> tuple:
    """Call NoteBot to improve a note's content. Returns suggested text without saving."""
    notes_dir, note_path, err = _resolve_note_path(project_name, filename)
    if err:
        return {"error": err}, 400

    if not note_path.exists():
        return {"error": f"Note '{filename}' not found."}, 404

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY is not set."}, 400

    try:
        NOTEBOT_PKG = REPO_ROOT / "bots" / "notebot"
        if str(NOTEBOT_PKG) not in sys.path:
            sys.path.insert(0, str(NOTEBOT_PKG))
        from notebot.analyzer import improve_note  # noqa: E402
        content = note_path.read_text(encoding="utf-8")
        improved = improve_note(content, title=filename)
        return {"improved": improved}, 200
    except Exception as e:
        return {"error": f"Improve failed: {e}"}, 500
