"""Reusable request parsing and dispatch helpers for the orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from orchestrator.bot_invoker import invoke_bot
from orchestrator.registry import Project, ProjectRegistry
from shared.llm import create_client
from shared.models import BotResult, ProjectScope

SYSTEM_PROMPT = """\
You are DevBot Orchestrator, an intelligent assistant that helps developers get information about their projects.

You have access to:
1. A project registry — list of known projects with their paths and scopes
2. TEAM bots (for code repositories and issue trackers):
   - gitbot: analyzes git history and provides summaries
   - qabot: suggests tests based on recent changes
   - pmbot: analyzes issues and generates sprint plans (requires GitLab or GitHub integration)
3. PERSONAL bots (for personal data files — journals, tasks, habits):
   - journalbot: analyzes a directory of markdown journal/notes files
   - taskbot: analyzes personal task lists (markdown checklists, todo.txt)
   - habitbot: analyzes habit tracking data (CSV or markdown tables)

CONTEXT DETECTION — detect which scope the user means from their phrasing:
- Personal signals: "my week", "my journal", "how am I doing", "my tasks", "my habits",
  "my notes", "my side project", "personal" → use personal projects and personal bots
- Team signals: project names, "issues", "sprint", "commits", "tests", "the team",
  specific team project names → use team projects and team bots
- If ambiguous and both scopes have matching projects, include "scope": null and ask
  for clarification in the explanation field.

When the user asks for information, you should:
1. Detect the scope (personal or team) from their phrasing
2. Identify which project they're referring to (match by name within that scope)
3. Determine which bot they need
4. Return a JSON response with the action to take

Response format:
{
  "action": "invoke_bot" | "list_projects" | "unknown",
  "bot": "gitbot" | "qabot" | "pmbot" | "journalbot" | "taskbot" | "habitbot" | null,
  "project": "project_name" | null,
  "scope": "team" | "personal" | null,
  "params": {
    "max_commits": 50,
    "pmbot_mode": "analyze" or "plan"
  },
  "explanation": "Brief explanation of what you'll do"
}

Examples:
- "get gitbot report for uni.li" → {"action": "invoke_bot", "bot": "gitbot", "project": "uni.li", "scope": "team", ...}
- "how was my week?" → {"action": "invoke_bot", "bot": "journalbot", "project": "<personal journal project>", "scope": "personal", ...}
- "check my tasks" → {"action": "invoke_bot", "bot": "taskbot", "project": "<personal task project>", "scope": "personal", ...}
- "how are my habits going?" → {"action": "invoke_bot", "bot": "habitbot", "project": "<personal habit project>", "scope": "personal", ...}
- "analyze issues for project X" → {"action": "invoke_bot", "bot": "pmbot", "project": "X", "scope": "team", "params": {"pmbot_mode": "analyze"}, ...}
- "create sprint plan for project Y" → {"action": "invoke_bot", "bot": "pmbot", "project": "Y", "scope": "team", "params": {"pmbot_mode": "plan"}, ...}
- "what projects do you know?" → {"action": "list_projects", "scope": null, ...}

IMPORTANT: pmbot only works if the project has GitLab or GitHub integration configured.
IMPORTANT: journalbot/taskbot/habitbot only work for personal-scope projects with the matching data source configured.

Be concise and helpful.
"""


@dataclass
class OrchestratorOutcome:
    """Structured result for a parsed user request."""

    action_plan: dict[str, Any]
    bot_result: BotResult | None = None
    projects: list[Project] = field(default_factory=list)
    error: str | None = None


def parse_user_request(user_message: str, available_projects: list[str]) -> dict[str, Any]:
    """Use Claude to parse a request and determine the next orchestrator action."""
    client = create_client()

    projects_list = ", ".join(available_projects) if available_projects else "none registered"
    user_prompt = f"""Available projects: {projects_list}

User request: {user_message}

What should I do? Respond with valid JSON only."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = message.content[0].text.strip()

    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {"action": "unknown", "explanation": "Could not parse request"}


def _parse_scope(scope_value: str | None) -> ProjectScope | None:
    if not scope_value:
        return None
    try:
        return ProjectScope(scope_value.lower())
    except ValueError:
        return None


def format_projects_markdown(projects: list[Project]) -> str:
    """Render a registry listing as markdown for alternate frontends like voicebot."""
    if not projects:
        return "No projects are currently registered."

    lines = ["## Registered Projects", ""]
    for project in sorted(projects, key=lambda item: (item.scope.value, item.name.lower())):
        description = f" — {project.description}" if project.description else ""
        lines.append(f"- **{project.name}** (`{project.scope.value}`){description}")
    return "\n".join(lines)


def process_user_request(user_message: str, registry: ProjectRegistry) -> OrchestratorOutcome:
    """Parse and execute a natural-language orchestrator request."""
    available_projects = [project.name for project in registry.list_projects()]

    try:
        action_plan = parse_user_request(user_message, available_projects)
    except Exception as exc:
        return OrchestratorOutcome(
            action_plan={"action": "unknown", "explanation": "Could not parse request"},
            error=f"Error parsing request: {exc}",
        )

    action = action_plan.get("action")
    params = action_plan.get("params", {})

    if action == "list_projects":
        scope = _parse_scope(action_plan.get("scope"))
        projects = registry.list_by_scope(scope) if scope else registry.list_projects()
        return OrchestratorOutcome(action_plan=action_plan, projects=projects)

    if action != "invoke_bot":
        return OrchestratorOutcome(
            action_plan=action_plan,
            error="Sorry, I couldn't understand that request.",
        )

    bot_name = action_plan.get("bot")
    project_name = action_plan.get("project")

    if not bot_name or not project_name:
        return OrchestratorOutcome(
            action_plan=action_plan,
            error="Could not determine which bot or project to use.",
        )

    project = registry.get_project(project_name)
    if not project:
        return OrchestratorOutcome(
            action_plan=action_plan,
            error=f"Project '{project_name}' not found. Use `orchestrator projects` to inspect registered names.",
        )

    if bot_name == "pmbot":
        if not project.has_gitlab() and not project.has_github():
            return OrchestratorOutcome(
                action_plan=action_plan,
                error=(
                    f"Project '{project.name}' has no GitLab or GitHub integration configured for pmbot."
                ),
            )
        bot_result = invoke_bot(
            bot_name,
            project=project,
            pmbot_mode=params.get("pmbot_mode", "analyze"),
        )
        return OrchestratorOutcome(action_plan=action_plan, bot_result=bot_result)

    if bot_name in ("journalbot", "taskbot", "habitbot", "notebot", "pagespeedbot"):
        bot_result = invoke_bot(bot_name, project=project)
        return OrchestratorOutcome(action_plan=action_plan, bot_result=bot_result)

    bot_result = invoke_bot(
        bot_name,
        project=project,
        max_commits=params.get("max_commits", 300),
    )
    return OrchestratorOutcome(action_plan=action_plan, bot_result=bot_result)
