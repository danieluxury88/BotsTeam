"""
IssueBot analyzer — two AI capabilities:
1. analyze()  — summarize issue patterns, recurring problems, project health
2. plan()     — generate a prioritized, effort-estimated sprint workload plan
"""

from __future__ import annotations

import json
import re

from shared import llm
from shared.models import (
    BotResult,
    BotStatus,
    EffortSize,
    Issue,
    IssuePriority,
    IssueSet,
    PlannedIssue,
    WorkloadPlan,
)

# ── Shared system prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are IssueBot, an expert software project manager and engineering lead.
You analyze GitLab and GitHub issues to help teams understand their backlog, identify patterns,
and plan work effectively.
Be concise, direct, and actionable. Format responses in clean Markdown.
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _format_issue_list(issues: list[Issue], max_issues: int = 60) -> str:
    """Compact text representation of issues for LLM prompts."""
    lines: list[str] = []
    for i in issues[:max_issues]:
        labels = f" | labels: {', '.join(i.labels)}" if i.labels else " | labels: none"
        assignee = (
            f" | assignees: @{', @'.join(i.assignees)}"
            if i.assignees
            else " | assignees: unassigned"
        )
        milestone = f" | milestone: {i.milestone}" if i.milestone else ""
        age = f" | {i.age_days}d old"
        desc = f"\n     {i.short_desc}" if i.short_desc else ""
        lines.append(
            f"#{i.iid} {i.title}{labels}{assignee}{milestone}{age}{desc}"
        )
    if len(issues) > max_issues:
        lines.append(f"... and {len(issues) - max_issues} more issues not shown.")
    return "\n".join(lines)


def _label_distribution(issues: list[Issue]) -> dict[str, int]:
    """Count label frequency across a list of issues."""
    label_dist: dict[str, int] = {}
    for issue in issues:
        for label in issue.labels:
            label_dist[label] = label_dist.get(label, 0) + 1
    return label_dist


def _label_summary(issues: list[Issue], max_labels: int = 15) -> str:
    """Human-readable label frequency summary for prompts."""
    label_dist = _label_distribution(issues)
    return ", ".join(
        f"{label} ({count})"
        for label, count in sorted(
            label_dist.items(),
            key=lambda item: (-item[1], item[0].lower()),
        )[:max_labels]
    )


def _render_open_tasks_by_assignee(open_issues: list[Issue]) -> str:
    """Render a deterministic assignee view of the current open backlog."""
    lines = ["## Open Tasks By Assignee", ""]

    if not open_issues:
        lines.append("No open tasks.")
        return "\n".join(lines)

    buckets: dict[str, list[Issue]] = {}
    for issue in open_issues:
        assignees = issue.assignees or ["Unassigned"]
        for assignee in assignees:
            buckets.setdefault(assignee, []).append(issue)

    assigned_names = sorted(
        (name for name in buckets if name != "Unassigned"),
        key=str.lower,
    )
    ordered_names = assigned_names + (["Unassigned"] if "Unassigned" in buckets else [])

    for assignee in ordered_names:
        heading = f"@{assignee}" if assignee != "Unassigned" else assignee
        items = sorted(
            buckets[assignee],
            key=lambda issue: (-issue.age_days, issue.iid),
        )
        lines.append(f"### {heading} ({len(items)})")
        for issue in items:
            link = f"[#{issue.iid}]({issue.web_url})" if issue.web_url else f"#{issue.iid}"
            labels = f" — labels: {', '.join(issue.labels[:4])}" if issue.labels else ""
            milestone = f" — milestone: {issue.milestone}" if issue.milestone else ""
            lines.append(
                f"- {link} **{issue.title}**{labels}{milestone} — {issue.age_days}d old"
            )
        lines.append("")

    return "\n".join(lines).rstrip()


# ── 1. Issue pattern analysis ────────────────────────────────────────────────

def analyze(issue_set: IssueSet) -> BotResult:
    """
    AI analysis of the full issue set:
    patterns, recurring problems, project health, team workload.
    """
    open_text   = _format_issue_list(issue_set.open_issues)
    closed_text = _format_issue_list(issue_set.closed_issues, max_issues=30)

    label_dist = _label_distribution(issue_set.issues)
    label_summary = _label_summary(issue_set.issues)

    stale = issue_set.stale()

    user_message = f"""\
Please analyze the issue tracker backlog for **{issue_set.project_name}**.

## Stats
- Open issues: {len(issue_set.open_issues)}
- Closed issues: {len(issue_set.closed_issues)}
- Stale open issues (no update >30 days): {len(stale)}
- All labels (by frequency): {label_summary or "none"}
- Assignees: {', '.join(issue_set.all_assignees) or "none"}

## Open Issues
{open_text or "No open issues."}

## Recently Closed Issues (sample)
{closed_text or "No closed issues."}

Please produce a structured report:
1. **Project Health** — overall assessment of the backlog
2. **Patterns & Recurring Problems** — themes you notice across issues
3. **Hotspots** — labels, areas, or components with the most issues
4. **Team Workload** — distribution across assignees, any imbalances
5. **Stale Issues** — highlight any open issues that need attention
6. **Recommendations** — 3-5 concrete actions to improve the backlog
"""

    try:
        report_md = llm.chat(
            system=SYSTEM_PROMPT,
            user=user_message,
            max_tokens=1500,
            bot_env_key="ISSUEBOT_MODEL",
        )
        report_md = f"{report_md.rstrip()}\n\n{_render_open_tasks_by_assignee(issue_set.open_issues)}"

        return BotResult(
            bot_name="issuebot",
            status=BotStatus.SUCCESS,
            summary=(
                f"{len(issue_set.open_issues)} open / "
                f"{len(issue_set.closed_issues)} closed issues analyzed "
                f"for {issue_set.project_name}"
            ),
            report_md=report_md,
            payload={
                "project": issue_set.project_name,
                "open": len(issue_set.open_issues),
                "closed": len(issue_set.closed_issues),
                "stale": len(stale),
                "labels": label_dist,
                "assignees": issue_set.all_assignees,
            },
        )

    except Exception as e:
        return BotResult.failure("issuebot", str(e))


# ── 2. Workload planner ──────────────────────────────────────────────────────

_PLAN_SYSTEM = """\
You are IssueBot acting as a sprint planner.
Your job is to take a list of open GitLab or GitHub issues and return a structured JSON workload plan.

Return ONLY valid JSON — no markdown fences, no preamble, no explanation.

JSON schema:
{
  "summary": "one paragraph overview of the plan",
  "warnings": ["list of concerns or risks"],
  "issues": [
    {
      "iid": 42,
      "priority": "critical|high|normal|low",
      "effort": "XS|S|M|L|XL",
      "rationale": "brief reason for priority and effort",
      "week": 1
    }
  ]
}

Priority guide:
- critical: blockers, security issues, data loss risks
- high: significant user impact, major bugs, overdue items
- normal: standard features and improvements
- low: nice-to-haves, minor tweaks, cosmetic issues

Effort guide (working hours):
- XS: < 2 hours
- S: half day (~4h)
- M: 1 day (~8h)
- L: 2-3 days
- XL: 1 week or more

Assign weeks (1 = this week, 2 = next week, etc.) based on priority and effort.
Assume one developer working on this, ~5 effective hours per day.

Label usage rules:
- Treat issue labels as first-class planning signals, not optional metadata.
- Use labels to infer severity, component ownership, risk, workflow stage, and dependency clusters.
- If labels suggest a blocker, regression, production risk, or cross-cutting subsystem, raise priority accordingly.
- If several issues share the same label cluster, group them logically across adjacent weeks when that reduces context switching.
- Do not invent meaning for labels that is not supported by the issue title/description, but do use reasonable tracker conventions such as bug, regression, security, performance, UX, backend, frontend, API, infra, blocked, urgent, and similar labels.
"""


def plan(issue_set: IssueSet) -> tuple[WorkloadPlan, BotResult]:
    """
    AI workload planner — prioritizes open issues, estimates effort,
    and returns a weekly sprint schedule.

    Returns both the structured WorkloadPlan and a BotResult for the orchestrator.
    """
    open_issues = issue_set.open_issues

    if not open_issues:
        plan_obj = WorkloadPlan(
            project_name=issue_set.project_name,
            total_open=0,
            summary="No open issues to plan.",
        )
        return plan_obj, BotResult(
            bot_name="issuebot",
            status=BotStatus.SKIPPED,
            summary="No open issues found — nothing to plan.",
            report_md="## ✅ No open issues\n\nThe backlog is empty.",
        )

    issues_text = _format_issue_list(open_issues)
    label_summary = _label_summary(open_issues, max_labels=20)
    labels_present = sum(1 for issue in open_issues if issue.labels)

    user_message = f"""\
Project: {issue_set.project_name}
Open issue label coverage: {labels_present}/{len(open_issues)} issues have labels
Open issue labels by frequency: {label_summary or "none"}

Open issues to plan ({len(open_issues)} total):

{issues_text}

When assigning priority and week, explicitly use issue labels where they add planning signal.
Return the JSON plan for all {len(open_issues)} issues.
"""

    try:
        raw_json = llm.chat(
            system=_PLAN_SYSTEM,
            user=user_message,
            max_tokens=2000,
            bot_env_key="ISSUEBOT_MODEL",
        )

        # Strip any accidental markdown fences
        clean = re.sub(r"```(?:json)?|```", "", raw_json).strip()
        data = json.loads(clean)

        # Build index of issues by iid for fast lookup
        issue_index = {i.iid: i for i in open_issues}

        planned: list[PlannedIssue] = []
        for item in data.get("issues", []):
            iid = item.get("iid")
            issue = issue_index.get(iid)
            if not issue:
                continue  # AI hallucinated an iid — skip

            try:
                priority = IssuePriority(item.get("priority", "normal"))
            except ValueError:
                priority = IssuePriority.NORMAL

            try:
                effort = EffortSize(item.get("effort", "M"))
            except ValueError:
                effort = EffortSize.M

            planned.append(PlannedIssue(
                issue=issue,
                priority=priority,
                effort=effort,
                rationale=item.get("rationale", ""),
                week=item.get("week", 1),
            ))

        plan_obj = WorkloadPlan(
            project_name=issue_set.project_name,
            total_open=len(open_issues),
            planned_issues=planned,
            warnings=data.get("warnings", []),
            summary=data.get("summary", ""),
        )

        report_md = _render_plan_markdown(plan_obj, open_issues)

        return plan_obj, BotResult(
            bot_name="issuebot",
            status=BotStatus.SUCCESS,
            summary=(
                f"Sprint plan for {issue_set.project_name}: "
                f"{len(planned)} issues across {len(plan_obj.by_week)} week(s)"
            ),
            report_md=report_md,
            payload={
                "project": issue_set.project_name,
                "total_planned": len(planned),
                "weeks": len(plan_obj.by_week),
                "warnings": plan_obj.warnings,
            },
        )

    except json.JSONDecodeError as e:
        return WorkloadPlan(
            project_name=issue_set.project_name,
            total_open=len(open_issues),
        ), BotResult.failure("issuebot", f"JSON parse error from planner: {e}")
    except Exception as e:
        return WorkloadPlan(
            project_name=issue_set.project_name,
            total_open=len(open_issues),
        ), BotResult.failure("issuebot", str(e))


def _render_plan_markdown(
    plan_obj: WorkloadPlan,
    open_issues: list[Issue] | None = None,
) -> str:
    """Render a WorkloadPlan to a clean markdown report."""
    lines: list[str] = []
    lines.append(f"# 🗓 Sprint Plan — {plan_obj.project_name}")
    lines.append(f"\n{plan_obj.summary}\n")

    if plan_obj.warnings:
        lines.append("## ⚠️ Warnings")
        for w in plan_obj.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Priority summary table
    lines.append("## Priority Overview")
    lines.append("")
    lines.append("| # | Issue | Labels | Priority | Effort | Rationale |")
    lines.append("|---|-------|--------|----------|--------|-----------|")

    priority_order = ["critical", "high", "normal", "low"]
    sorted_issues = sorted(
        plan_obj.planned_issues,
        key=lambda pi: (priority_order.index(pi.priority.value), pi.week or 99),
    )

    priority_icons = {
        "critical": "🔴",
        "high":     "🟠",
        "normal":   "🟡",
        "low":      "🟢",
    }

    for pi in sorted_issues:
        icon = priority_icons.get(pi.priority.value, "⚪")
        url = pi.issue.web_url
        link = f"[#{pi.issue.iid}]({url})" if url else f"#{pi.issue.iid}"
        title = pi.issue.title[:55] + ("…" if len(pi.issue.title) > 55 else "")
        labels = ", ".join(pi.issue.labels[:3]) if pi.issue.labels else "—"
        rationale = pi.rationale[:70] + ("…" if len(pi.rationale) > 70 else "")
        lines.append(
            f"| {link} | {title} | {labels} | {icon} {pi.priority.value} | "
            f"`{pi.effort.value}` | {rationale} |"
        )

    lines.append("")

    # Weekly schedule
    lines.append("## 📅 Weekly Schedule")
    for week_num, week_items in plan_obj.by_week.items():
        label = f"Week {week_num}" if week_num < 99 else "Backlog (unscheduled)"
        lines.append(f"\n### {label}")

        effort_hours = {"XS": 1.5, "S": 4, "M": 8, "L": 20, "XL": 40}
        total_h = sum(effort_hours.get(pi.effort.value, 8) for pi in week_items)
        lines.append(f"*Estimated load: ~{total_h:.0f}h*\n")

        for pi in sorted(week_items, key=lambda x: priority_order.index(x.priority.value)):
            icon = priority_icons.get(pi.priority.value, "⚪")
            url = pi.issue.web_url
            link = f"[#{pi.issue.iid}]({url})" if url else f"#{pi.issue.iid}"
            assignee = f" — @{', '.join(pi.issue.assignees)}" if pi.issue.assignees else ""
            labels = f" — labels: {', '.join(pi.issue.labels[:4])}" if pi.issue.labels else ""
            lines.append(
                f"- {icon} {link} **{pi.issue.title}** "
                f"`{pi.effort.value}`{assignee}{labels}"
            )

    source_issues = open_issues if open_issues is not None else [pi.issue for pi in plan_obj.planned_issues]
    lines.append("")
    lines.append(_render_open_tasks_by_assignee(source_issues))

    return "\n".join(lines)


# ── 3. Issue description reviewer ────────────────────────────────────────────

_REVIEW_BASE_SYSTEM = """\
You are an expert technical writer specializing in software project management.
Your job is to improve GitLab and GitHub issue descriptions to make them clearer, more complete,
and more actionable for developers.

Keep the same intent and technical content — only improve structure, clarity,
and completeness. Add sections like Steps to Reproduce, Expected Behavior,
Acceptance Criteria, or Technical Notes when appropriate and inferable.
"""

_REVIEW_SINGLE_SYSTEM = _REVIEW_BASE_SYSTEM + """\
Return ONLY the improved description as markdown text.
Do not include any preamble, explanation, or metadata — just the improved content.
"""

_REVIEW_BATCH_SYSTEM = _REVIEW_BASE_SYSTEM + """\
Return ONLY valid JSON — no markdown fences, no preamble, no explanation.

JSON schema:
[
  {
    "iid": 42,
    "improved_description": "The full improved description text..."
  }
]
"""

_REVIEW_BATCH_SIZE = 10


def _review_single(issue: "Issue", project_name: str) -> str:
    """
    Ask Claude to improve a single issue's description.
    Uses plain text response — more reliable than JSON for complex markdown content.
    Returns the improved description string, or "" on failure.
    """
    user_message = (
        f"Project: {project_name}\n\n"
        f"Issue #{issue.iid}: {issue.title}\n\n"
        f"Current description:\n{issue.description or '(no description)'}\n\n"
        f"Return only the improved description as markdown."
    )
    try:
        return llm.chat(
            system=_REVIEW_SINGLE_SYSTEM,
            user=user_message,
            max_tokens=2000,
            bot_env_key="ISSUEBOT_MODEL",
        ).strip()
    except Exception:
        return ""


def _review_batch(batch: "list[Issue]", project_name: str) -> "dict[int, str]":
    """
    Ask Claude to improve descriptions for multiple issues at once.
    Returns a dict of iid → improved_description.
    Falls back to empty strings on parse failure.
    """
    issues_payload = [
        f"Issue #{i.iid}: {i.title}\nCurrent description:\n{i.description or '(no description)'}"
        for i in batch
    ]
    user_message = (
        f"Project: {project_name}\n\n"
        + "\n\n---\n\n".join(issues_payload)
        + f"\n\nReturn a JSON array with improved descriptions for all {len(batch)} issues."
    )
    try:
        raw = llm.chat(
            system=_REVIEW_BATCH_SYSTEM,
            user=user_message,
            max_tokens=4000,
            bot_env_key="ISSUEBOT_MODEL",
        )
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        data = json.loads(clean)
        return {item["iid"]: item["improved_description"] for item in data}
    except (json.JSONDecodeError, KeyError, Exception):
        return {}


def review(issue_set: IssueSet) -> list[dict]:
    """
    AI review of issue descriptions — generates improved versions.

    Single issues use a plain-text response (reliable for any markdown content).
    Multiple issues are batched and use a JSON response.

    Returns a list of dicts with keys:
        iid (int), title (str), original (str), improved (str), web_url (str)
    """
    issues = issue_set.issues
    if not issues:
        return []

    results: list[dict] = []

    for batch_start in range(0, len(issues), _REVIEW_BATCH_SIZE):
        batch = issues[batch_start : batch_start + _REVIEW_BATCH_SIZE]

        if len(batch) == 1:
            # Single issue: plain text — avoids JSON escaping issues with markdown content
            i = batch[0]
            improved = _review_single(i, issue_set.project_name)
            results.append({
                "iid": i.iid,
                "title": i.title,
                "original": i.description or "",
                "improved": improved,
                "web_url": i.web_url,
            })
        else:
            # Multiple issues: JSON batch
            improved_by_iid = _review_batch(batch, issue_set.project_name)
            for i in batch:
                results.append({
                    "iid": i.iid,
                    "title": i.title,
                    "original": i.description or "",
                    "improved": improved_by_iid.get(i.iid, ""),
                    "web_url": i.web_url,
                })

    return results


# ── Programmatic API for orchestrator ────────────────────────────────────────

def get_bot_result(
    issue_set: IssueSet,
    mode: str = "analyze",
    project_name: str | None = None,
) -> BotResult:
    """
    Programmatic API for calling pmbot from other bots (e.g., orchestrator).

    Args:
        issue_set: IssueSet containing GitLab issues to analyze/plan
        mode: "analyze" for issue analysis, "plan" for sprint planning
        project_name: Optional project name for auto-saving reports

    Returns:
        BotResult with analysis or sprint plan
    """
    if mode == "analyze":
        result = analyze(issue_set)
    elif mode == "plan":
        _plan_obj, result = plan(issue_set)
    elif mode == "review":
        reviews = review(issue_set)
        reviewed = len(reviews)
        with_content = sum(1 for r in reviews if r["improved"])
        lines = [f"# Issue Description Review — {issue_set.project_name}\n"]
        for r in reviews:
            lines.append(f"## #{r['iid']}: {r['title']}\n")
            lines.append(f"**Original:**\n\n{r['original'] or '*(no description)*'}\n")
            lines.append(f"**Improved:**\n\n{r['improved'] or '*(no suggestion)*'}\n")
            lines.append("---\n")
        result = BotResult(
            bot_name="issuebot",
            status=BotStatus.SUCCESS if with_content else BotStatus.PARTIAL,
            summary=f"Reviewed {reviewed} issue descriptions for {issue_set.project_name}",
            report_md="\n".join(lines),
            payload={"project": issue_set.project_name, "reviewed": reviewed},
        )
    else:
        return BotResult(
            bot_name="issuebot",
            status=BotStatus.ERROR,
            summary=f"Unknown mode: {mode}. Use 'analyze', 'plan', or 'review'.",
            report_md="",
        )

    # Auto-save report if project_name is provided
    if project_name and result.report_md:
        from shared.data_manager import save_report
        latest, timestamped = save_report(
            project_name,
            "pmbot",
            result.report_md,
            save_latest=True,
            save_timestamped=True,
        )
        if not result.payload:
            result.payload = {}
        result.payload["report_saved"] = {
            "latest": str(latest),
            "timestamped": str(timestamped) if timestamped else None,
        }

    return result
