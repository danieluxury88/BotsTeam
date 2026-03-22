"""Programmatic PMBot runner for orchestrator and other bots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from project_manager.analyzer import (
    get_bot_result as get_issue_set_result,
    review,
)
from shared.github_client import GitHubClient
from shared.gitlab_client import GitLabClient
from shared.issue_tracker import UnsupportedIssueTrackerCapabilityError
from shared.models import (
    BotResult,
    BotStatus,
    IssueDraft,
    IssueSet,
    IssueState,
    IssueTrackerAccessReport,
    IssueTrackerPlatform,
)


@dataclass
class IssueTrackerTarget:
    """Resolved issue tracker details for PMBot actions."""

    client: GitHubClient | GitLabClient
    target_id: str
    source_name: str
    platform: IssueTrackerPlatform

    @property
    def source_label(self) -> str:
        return "GitHub" if self.platform == IssueTrackerPlatform.GITHUB else "GitLab"


def _as_list(value: list[str] | tuple[str, ...] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]

    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            for part in item.split(","):
                cleaned = part.strip()
                if cleaned and cleaned not in result:
                    result.append(cleaned)
    return result


def _resolve_issue_state(value: str | IssueState | None, default: IssueState) -> IssueState:
    if isinstance(value, IssueState):
        return value
    if not value:
        return default

    state_map = {
        "open": IssueState.OPEN,
        "opened": IssueState.OPEN,
        "closed": IssueState.CLOSED,
        "all": IssueState.ALL,
    }
    return state_map.get(value.lower(), default)


def _resolve_target(
    *,
    project_name: str | None = None,
    gitlab_project_id: str | None = None,
    gitlab_url: str | None = None,
    gitlab_token: str | None = None,
    github_repo: str | None = None,
    github_token: str | None = None,
    github_base_url: str | None = None,
) -> IssueTrackerTarget:
    """Resolve PMBot input into a configured issue-tracker target."""
    if github_repo:
        return IssueTrackerTarget(
            client=GitHubClient(token=github_token, base_url=github_base_url),
            target_id=github_repo,
            source_name=project_name or github_repo,
            platform=IssueTrackerPlatform.GITHUB,
        )

    if gitlab_project_id:
        return IssueTrackerTarget(
            client=GitLabClient(token=gitlab_token, url=gitlab_url),
            target_id=gitlab_project_id,
            source_name=project_name or gitlab_project_id,
            platform=IssueTrackerPlatform.GITLAB,
        )

    raise ValueError("PMBot requires either a GitHub repository or GitLab project ID.")


def _fetch_issue_set(
    target: IssueTrackerTarget,
    *,
    state: IssueState,
    max_issues: int,
) -> IssueSet:
    return target.client.fetch_issues(target.target_id, state=state, max_issues=max_issues)


def _get_single_issue_set(target: IssueTrackerTarget, issue_iid: int) -> IssueSet:
    issue = target.client.get_issue(target.target_id, issue_iid)
    return IssueSet(
        project_id=target.target_id,
        project_name=target.source_name,
        fetched_at=datetime.now(tz=timezone.utc),
        issues=[issue],
    )


def _render_create_report(target: IssueTrackerTarget, issue) -> str:
    lines = [
        f"# New Issue Created — {target.source_name}",
        "",
        f"- Tracker: {target.source_label}",
        f"- Issue: #{issue.iid}",
        f"- Title: {issue.title}",
    ]
    if issue.web_url:
        lines.append(f"- URL: {issue.web_url}")
    if issue.labels:
        lines.append(f"- Labels: {', '.join(issue.labels)}")
    if issue.assignees:
        lines.append(f"- Assignees: {', '.join(issue.assignees)}")
    return "\n".join(lines)


def _render_dry_run_report(target: IssueTrackerTarget, draft: IssueDraft) -> str:
    lines = [
        f"# Issue Draft — {target.source_name}",
        "",
        f"- Tracker: {target.source_label}",
        f"- Title: {draft.title}",
        f"- Labels: {', '.join(draft.labels) or 'none'}",
        f"- Assignees: {', '.join(draft.assignees) or 'none'}",
        "",
        "## Description",
        "",
        draft.description or "_(empty)_",
    ]
    return "\n".join(lines)


def _render_access_report(target: IssueTrackerTarget, report: IssueTrackerAccessReport) -> str:
    lines = [
        f"# Issue Tracker Access Check — {target.source_name}",
        "",
        f"- Tracker: {target.source_label}",
        f"- Target: {report.target_name}",
    ]
    if report.authenticated_as:
        lines.append(f"- Authenticated as: {report.authenticated_as}")
    lines.append("")
    lines.append("| Capability | PMBot | Token | Effective | Detail |")
    lines.append("| --- | --- | --- | --- | --- |")

    for status in report.capability_statuses:
        token_label = (
            "verified"
            if status.authorized is True
            else "denied"
            if status.authorized is False
            else "unknown"
        )
        lines.append(
            "| "
            f"{status.capability.value.replace('_', ' ')} | "
            f"{'supported' if status.supported else 'not yet'} | "
            f"{token_label} | "
            f"{status.effective_status} | "
            f"{status.detail} |"
        )

    return "\n".join(lines)


def _create_issue_result(
    target: IssueTrackerTarget,
    *,
    title: str,
    description: str = "",
    labels: list[str] | tuple[str, ...] | str | None = None,
    assignees: list[str] | tuple[str, ...] | str | None = None,
    dry_run: bool = False,
) -> BotResult:
    if not title.strip():
        return BotResult(
            bot_name="issuebot",
            status=BotStatus.ERROR,
            summary="PMBot create mode requires a non-empty title.",
            report_md="",
        )

    draft = IssueDraft(
        title=title.strip(),
        description=description,
        labels=_as_list(labels),
        assignees=_as_list(assignees),
    )

    if dry_run:
        return BotResult(
            bot_name="issuebot",
            status=BotStatus.SUCCESS,
            summary=f"Prepared issue draft for {target.source_name}: {draft.title}",
            report_md=_render_dry_run_report(target, draft),
            payload={"draft": draft, "dry_run": True},
        )

    created = target.client.create_issue(target.target_id, draft)
    return BotResult(
        bot_name="issuebot",
        status=BotStatus.SUCCESS,
        summary=f"Created issue #{created.iid} in {target.source_name}: {created.title}",
        report_md=_render_create_report(target, created),
        payload={
            "issue": created,
            "tracker": target.platform.value,
            "target_id": target.target_id,
        },
    )


def _check_issue_tracker_result(target: IssueTrackerTarget) -> BotResult:
    report = target.client.probe_capabilities(target.target_id)
    blocked = sum(1 for status in report.capability_statuses if status.effective_status == "blocked")
    unsupported = sum(1 for status in report.capability_statuses if status.effective_status == "unsupported")

    summary = f"Verified issue-tracker access for {target.source_name}"
    status = BotStatus.SUCCESS
    if blocked and unsupported:
        status = BotStatus.PARTIAL
        summary = (
            f"Verified issue-tracker access for {target.source_name} "
            f"with {blocked} blocked and {unsupported} unsupported capabilities"
        )
    elif blocked:
        status = BotStatus.PARTIAL
        summary = (
            f"Verified issue-tracker access for {target.source_name} "
            f"with {blocked} blocked capabilities"
        )
    elif unsupported:
        summary = (
            f"Verified issue-tracker access for {target.source_name} "
            f"with {unsupported} unsupported capabilities"
        )

    return BotResult(
        bot_name="issuebot",
        status=status,
        summary=summary,
        report_md=_render_access_report(target, report),
        payload={"report": report},
    )


def _review_issue_set_result(
    target: IssueTrackerTarget,
    issue_set: IssueSet,
    *,
    apply_updates: bool = False,
) -> BotResult:
    reviews = review(issue_set)
    reviewed = len(reviews)
    with_content = sum(1 for item in reviews if item["improved"])

    updated = 0
    if apply_updates:
        for item in reviews:
            if not item["improved"]:
                continue
            target.client.update_issue_description(
                target.target_id,
                item["iid"],
                item["improved"],
            )
            updated += 1

    lines = [f"# Issue Description Review — {issue_set.project_name}", ""]
    if apply_updates:
        lines.append(f"*Applied updates to {updated} issue(s).*")
        lines.append("")

    for item in reviews:
        lines.append(f"## #{item['iid']}: {item['title']}")
        lines.append("")
        lines.append("**Original:**")
        lines.append("")
        lines.append(item["original"] or "*(no description)*")
        lines.append("")
        lines.append("**Improved:**")
        lines.append("")
        lines.append(item["improved"] or "*(no suggestion)*")
        lines.append("")
        lines.append("---")
        lines.append("")

    status = BotStatus.SUCCESS if with_content else BotStatus.PARTIAL
    summary = f"Reviewed {reviewed} issue descriptions for {issue_set.project_name}"
    if apply_updates:
        summary = f"Reviewed and updated {updated} issues for {issue_set.project_name}"

    return BotResult(
        bot_name="issuebot",
        status=status,
        summary=summary,
        report_md="\n".join(lines).strip(),
        payload={
            "project": issue_set.project_name,
            "reviewed": reviewed,
            "updated": updated,
            "apply_updates": apply_updates,
        },
    )


def get_bot_result(
    *,
    project_name: str | None = None,
    gitlab_project_id: str | None = None,
    gitlab_url: str | None = None,
    gitlab_token: str | None = None,
    github_repo: str | None = None,
    github_token: str | None = None,
    github_base_url: str | None = None,
    mode: str = "analyze",
    max_issues: int = 200,
    state: str | IssueState | None = None,
    issue_iid: int | None = None,
    title: str = "",
    description: str = "",
    labels: list[str] | tuple[str, ...] | str | None = None,
    assignees: list[str] | tuple[str, ...] | str | None = None,
    dry_run: bool = False,
    apply_updates: bool = False,
) -> BotResult:
    """Run a PMBot capability by resolving its issue tracker internally."""
    try:
        target = _resolve_target(
            project_name=project_name,
            gitlab_project_id=gitlab_project_id,
            gitlab_url=gitlab_url,
            gitlab_token=gitlab_token,
            github_repo=github_repo,
            github_token=github_token,
            github_base_url=github_base_url,
        )

        if mode == "create":
            return _create_issue_result(
                target,
                title=title,
                description=description,
                labels=labels,
                assignees=assignees,
                dry_run=dry_run,
            )

        if mode == "check":
            return _check_issue_tracker_result(target)

        if issue_iid is not None:
            issue_set = _get_single_issue_set(target, issue_iid)
        else:
            default_state = IssueState.ALL if mode == "analyze" else IssueState.OPEN
            issue_set = _fetch_issue_set(
                target,
                state=_resolve_issue_state(state, default_state),
                max_issues=max_issues,
            )

        if mode == "review":
            return _review_issue_set_result(
                target,
                issue_set,
                apply_updates=apply_updates,
            )

        return get_issue_set_result(
            issue_set,
            mode=mode,
            project_name=project_name,
        )
    except UnsupportedIssueTrackerCapabilityError as e:
        return BotResult.failure("issuebot", str(e))
    except Exception as e:
        return BotResult.failure("issuebot", str(e))
