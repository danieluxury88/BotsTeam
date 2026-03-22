"""Shared issue-tracker capability contracts."""

from __future__ import annotations

from typing import Protocol

from shared.models import (
    IssueTrackerAccessReport,
    IssueTrackerCapability,
    IssueTrackerPlatform,
)


class UnsupportedIssueTrackerCapabilityError(NotImplementedError):
    """Raised when a tracker backend does not support a requested operation."""


class IssueTrackerClient(Protocol):
    """Protocol for issue tracker clients shared by multiple bots."""

    platform: IssueTrackerPlatform

    def capabilities(self) -> frozenset[IssueTrackerCapability]:
        """Return the operations supported by this client."""

    def supports(self, capability: IssueTrackerCapability) -> bool:
        """Check whether the client supports a capability."""

    def probe_capabilities(self, target_id: str) -> IssueTrackerAccessReport:
        """Verify runtime tracker access for a concrete repository or project."""
