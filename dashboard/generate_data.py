#!/usr/bin/env python3
"""
Generate JSON data files for DevBots Dashboard
Scans the data/ directory and projects registry to create index files
"""

import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

# Paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
PERSONAL_DIR = DATA_DIR / "personal"
PROJECTS_JSON = DATA_DIR / "projects.json"
PERSONAL_PROJECTS_JSON = PERSONAL_DIR / "projects.json"
DASHBOARD_DIR = REPO_ROOT / "dashboard" / "data"

# Ensure shared is importable when running as a standalone script
_SHARED_PKG = REPO_ROOT / "shared"
if str(_SHARED_PKG) not in sys.path:
    sys.path.insert(0, str(_SHARED_PKG))

from shared.bot_registry import personal_bots, team_bots, all_bots, to_json as _bots_to_json, BOTS as _BOT_REGISTRY  # noqa: E402

TEAM_BOTS = team_bots()
PERSONAL_BOTS = personal_bots()
ALL_BOTS = all_bots()


# ---------------------------------------------------------------------------
# Calendar event abstraction
# ---------------------------------------------------------------------------

@dataclass
class CalendarEvent:
    """A single event to display on the calendar."""
    date: str        # "YYYY-MM-DD"
    type: str        # "report_run" | future: "issue_due" | "commit" | "journal_entry"
    title: str
    project_id: str
    scope: str       # "team" | "personal"
    color: str       # CSS class suffix — matches .cal-color-{color}
    meta: dict       # type-specific payload


class ReportRunEventSource:
    """Converts report index entries into CalendarEvents (one per report run)."""

    def __init__(self, reports: List[Dict[str, Any]]):
        self._reports = reports

    def get_events(self) -> List[CalendarEvent]:
        events = []
        for report in self._reports:
            timestamp = report.get("timestamp", "")
            if not timestamp:
                continue
            date = timestamp[:10]  # "YYYY-MM-DD"
            bot = report.get("bot", "")
            project_name = report.get("project_name") or report.get("project_id", "")
            bot_meta = _BOT_REGISTRY.get(bot)
            bot_display = f"{bot_meta.icon} {bot_meta.name}" if bot_meta else bot
            events.append(CalendarEvent(
                date=date,
                type="report_run",
                title=f"{bot_display} · {project_name}",
                project_id=report.get("project_id", ""),
                scope=report.get("scope", "team"),
                color=bot,  # matches .cal-color-{bot} CSS class
                meta={
                    "bot": bot,
                    "status": report.get("status", ""),
                    "summary": report.get("summary", "")[:150],
                    "path": report.get("path", ""),
                    "report_id": report.get("id", ""),
                },
            ))
        return events

# Future event sources (add here when bots export structured event data):
# class IssueDueDateEventSource:   reads pmbot latest_events.json
# class CommitActivityEventSource: reads gitbot latest_events.json
# class JournalEntryEventSource:   reads journalbot latest_events.json


class DashboardDataGenerator:
    """Generate dashboard data from DevBots reports"""

    def __init__(self):
        self.projects = []
        self.reports = []
        self.bots = ALL_BOTS

    def _load_registry(self, registry_path: Path, scope: str) -> List[Dict[str, Any]]:
        """Load projects from a registry JSON file and tag them with scope."""
        if not registry_path.exists():
            return []
        try:
            with open(registry_path, "r") as f:
                data = json.load(f)
            projects = []
            for key, proj in data.items():
                proj["id"] = key
                proj["scope"] = scope
                if "name" not in proj:
                    proj["name"] = key
                # Map registry field names to dashboard field names
                if "gitlab_project_id" in proj and "gitlab_id" not in proj:
                    proj["gitlab_id"] = proj["gitlab_project_id"]
                projects.append(proj)
            return projects
        except Exception as e:
            print(f"❌ Error loading registry {registry_path}: {e}")
            return []

    def load_projects(self) -> List[Dict[str, Any]]:
        """Load projects from both team and personal registries."""
        team = self._load_registry(PROJECTS_JSON, "team")
        personal = self._load_registry(PERSONAL_PROJECTS_JSON, "personal")

        if not team and not personal:
            print(f"⚠️  No projects found in {PROJECTS_JSON} or {PERSONAL_PROJECTS_JSON}")
            print("   Using empty project list.")

        return team + personal

    def _report_base_dir(self, project_id: str, is_personal: bool) -> Path:
        """Return the reports base directory for a project."""
        if is_personal:
            return PERSONAL_DIR / project_id / "reports"
        return DATA_DIR / project_id / "reports"

    def _report_url_prefix(self, project_id: str, is_personal: bool) -> str:
        """Return the URL prefix for a project's reports (served by DashboardHandler)."""
        if is_personal:
            return f"reports/personal/{project_id}"
        return f"reports/{project_id}"

    def scan_reports(self, project_id: str, is_personal: bool = False) -> List[Dict[str, Any]]:
        """Scan report directory for a project."""
        reports = []
        project_data_dir = self._report_base_dir(project_id, is_personal)

        if not project_data_dir.exists():
            return reports

        bots_to_scan = PERSONAL_BOTS if is_personal else TEAM_BOTS

        for bot in bots_to_scan:
            bot_reports_dir = project_data_dir / bot
            if not bot_reports_dir.exists():
                continue

            for report_file in bot_reports_dir.glob("*.md"):
                if report_file.name == "latest.md":
                    continue

                report = self.parse_report(
                    project_id, bot, report_file, is_personal=is_personal
                )
                if report:
                    reports.append(report)

        return reports

    def parse_report(
        self,
        project_id: str,
        bot: str,
        report_path: Path,
        is_personal: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Parse a report file and extract metadata"""
        try:
            stat = report_path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)

            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read(500)
                summary = self.extract_summary(content)

            # Parse timestamp from filename (e.g., 2026-02-16T18-30-00.md)
            timestamp_str = report_path.stem
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("-", ":", 2))
            except Exception:
                timestamp = mtime

            status = self.determine_status(content)
            report_id = f"{bot}-{project_id}-{timestamp_str}"
            url_prefix = self._report_url_prefix(project_id, is_personal)
            url_path = f"{url_prefix}/{bot}/{report_path.name}"

            return {
                "id": report_id,
                "bot": bot,
                "project_id": project_id,
                "scope": "personal" if is_personal else "team",
                "timestamp": timestamp.isoformat(),
                "status": status,
                "summary": summary,
                "path": url_path,
                "size_bytes": stat.st_size,
            }

        except Exception as e:
            print(f"⚠️  Error parsing {report_path}: {e}")
            return None

    def extract_summary(self, content: str) -> str:
        """Extract a summary from report content"""
        lines = content.split("\n")
        for line in lines:
            if line.startswith("#"):
                continue
            if line.strip():
                return line.strip()[:200]
        return "No summary available"

    def determine_status(self, content: str) -> str:
        """Determine report status from content"""
        content_lower = content.lower()
        if "❌" in content or "failed" in content_lower or "error" in content_lower:
            return "failed"
        elif "⚠️" in content or "warning" in content_lower or "partial" in content_lower:
            return "partial"
        return "success"

    def generate_projects_json(self, projects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate projects.json with enriched data"""
        enriched_projects = []

        for project in projects:
            project_id = project.get("id")
            if not project_id:
                continue

            is_personal = project.get("scope") == "personal"
            reports = self.scan_reports(project_id, is_personal=is_personal)

            last_activity = None
            if reports:
                last_activity = max(r["timestamp"] for r in reports)

            bots_run = list(set(r["bot"] for r in reports))

            enriched = {
                "id": project_id,
                "name": project.get("name", project_id),
                "path": project.get("path", ""),
                "description": project.get("description", ""),
                "scope": project.get("scope", "team"),
                "gitlab_id": project.get("gitlab_id"),
                "gitlab_url": project.get("gitlab_url"),
                "github_repo": project.get("github_repo"),
                # Personal data source fields
                "notes_dir": project.get("notes_dir"),
                "task_file": project.get("task_file"),
                "habit_file": project.get("habit_file"),
                "last_activity": last_activity,
                "reports_count": len(reports),
                "bots_run": bots_run,
            }

            enriched_projects.append(enriched)

        return {
            "projects": enriched_projects,
            "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def generate_index_json(self) -> Dict[str, Any]:
        """Generate master reports index"""
        all_reports = []

        for project in self.projects:
            project_id = project.get("id")
            if not project_id:
                continue

            is_personal = project.get("scope") == "personal"
            reports = self.scan_reports(project_id, is_personal=is_personal)
            for report in reports:
                report["project_name"] = project.get("name", project_id)
                all_reports.append(report)

        all_reports.sort(key=lambda r: r["timestamp"], reverse=True)

        return {
            "reports": all_reports,
            "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total_reports": len(all_reports),
        }

    def generate_dashboard_json(self) -> Dict[str, Any]:
        """Generate dashboard.json with statistics"""
        all_reports = self.reports

        active_projects = sum(1 for p in self.projects if p.get("last_activity"))
        personal_count = sum(1 for p in self.projects if p.get("scope") == "personal")
        team_count = len(self.projects) - personal_count

        recent_activity = [
            {
                "timestamp": r["timestamp"],
                "bot": r["bot"],
                "project": r["project_name"],
                "scope": r.get("scope", "team"),
                "status": r["status"],
                "summary": r["summary"][:100],
            }
            for r in all_reports[:10]
        ]

        return {
            "version": "1.0.0",
            "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "statistics": {
                "total_projects": len(self.projects),
                "team_projects": team_count,
                "personal_projects": personal_count,
                "active_projects": active_projects,
                "total_reports": len(all_reports),
                "total_bots": len(ALL_BOTS),
            },
            "recent_activity": recent_activity,
        }

    def save_json(self, filename: str, data: Dict[str, Any]):
        """Save JSON data to file"""
        output_path = DASHBOARD_DIR / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✅ Generated: {output_path}")

    def generate_bots_json(self) -> Dict[str, Any]:
        """Generate bots.json from the bot registry."""
        return {
            "bots": _bots_to_json(),
            "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def generate_calendar_json(self) -> Dict[str, Any]:
        """Generate calendar.json with all events from all sources."""
        sources = [
            ReportRunEventSource(self.reports),
            # Future sources registered here:
            # IssueDueDateEventSource(self.reports),
            # CommitActivityEventSource(self.reports),
        ]

        all_events: List[CalendarEvent] = []
        for source in sources:
            all_events.extend(source.get_events())

        all_events.sort(key=lambda e: e.date, reverse=True)
        event_types = sorted({e.type for e in all_events})

        return {
            "events": [asdict(e) for e in all_events],
            "event_types": event_types,
            "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def run(self):
        """Main execution"""
        print("🤖 DevBots Dashboard Data Generator")
        print("=" * 50)

        print("\n🤖 Generating bots.json...")
        self.save_json("bots.json", self.generate_bots_json())

        print("\n📁 Loading projects...")
        projects = self.load_projects()
        team_count = sum(1 for p in projects if p.get("scope") == "team")
        personal_count = sum(1 for p in projects if p.get("scope") == "personal")
        print(f"   Found {len(projects)} projects ({team_count} team, {personal_count} personal)")

        print("\n📊 Generating projects.json...")
        projects_data = self.generate_projects_json(projects)
        self.projects = projects_data["projects"]
        self.save_json("projects.json", projects_data)

        print("\n📋 Generating index.json...")
        index_data = self.generate_index_json()
        self.reports = index_data["reports"]
        self.save_json("index.json", index_data)

        print("\n📈 Generating dashboard.json...")
        dashboard_data = self.generate_dashboard_json()
        self.save_json("dashboard.json", dashboard_data)

        print("\n📅 Generating calendar.json...")
        calendar_data = self.generate_calendar_json()
        self.save_json("calendar.json", calendar_data)

        print("\n✨ Done! Dashboard data generated successfully.")
        print(f"\n📊 Summary:")
        print(f"   Bots:     {len(ALL_BOTS)} registered")
        print(f"   Projects: {len(self.projects)} ({team_count} team, {personal_count} personal)")
        print(f"   Reports:  {len(self.reports)}")
        print(f"   Output:   {DASHBOARD_DIR}")


if __name__ == "__main__":
    generator = DashboardDataGenerator()
    generator.run()
