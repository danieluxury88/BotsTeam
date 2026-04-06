"""HTTP client for sending payloads to Microsoft Teams webhooks/workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request


@dataclass(frozen=True)
class TeamsWebhookResponse:
    """Normalized response from a Teams webhook/workflow POST."""

    status_code: int
    body: str


def send_webhook(
    webhook_url: str,
    payload: dict[str, Any],
    timeout: int,
) -> TeamsWebhookResponse:
    """Send a JSON payload to a Teams webhook/workflow endpoint."""
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            return TeamsWebhookResponse(
                status_code=response.getcode(),
                body=response.read().decode("utf-8", errors="replace"),
            )
    except error.HTTPError as exc:
        return TeamsWebhookResponse(
            status_code=exc.code,
            body=exc.read().decode("utf-8", errors="replace"),
        )
