"""The dashboard server must stay loopback-only and same-origin (no CORS, Host/Origin guard)."""

from __future__ import annotations

import http.client
import json
import sys
import threading
from pathlib import Path

import pytest

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

import server  # noqa: E402


@pytest.fixture()
def running_server():
    httpd = server.make_server(port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _request(httpd, method: str, path: str, headers: dict[str, str] | None = None, body: dict | None = None):
    port = httpd.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    payload = json.dumps(body) if body is not None else None
    try:
        conn.request(method, path, body=payload, headers=headers or {})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def test_server_binds_loopback_only(running_server) -> None:
    assert running_server.server_address[0] == "127.0.0.1"
    assert server.HOST == "127.0.0.1"


def test_responses_carry_no_cors_headers(running_server) -> None:
    status, headers, _ = _request(running_server, "GET", "/api/settings")

    assert status == 200
    assert not any(name.lower().startswith("access-control-") for name in headers)


def test_foreign_host_header_is_rejected(running_server) -> None:
    status, _, body = _request(running_server, "GET", "/api/settings", headers={"Host": "attacker.example:8080"})

    assert status == 403
    assert "same-origin" in json.loads(body)["error"]


@pytest.mark.parametrize("origin", ["https://attacker.example", "null", "http://localhost:1"])
def test_cross_origin_mutation_is_rejected(running_server, origin: str) -> None:
    port = running_server.server_address[1]
    status, _, _ = _request(
        running_server,
        "PUT",
        "/api/settings",
        headers={"Host": f"localhost:{port}", "Origin": origin, "Content-Type": "text/plain"},
        body={"provider": "openai"},
    )

    assert status == 403


def test_same_origin_request_is_allowed(running_server) -> None:
    port = running_server.server_address[1]
    status, _, body = _request(
        running_server,
        "GET",
        "/api/settings",
        headers={"Host": f"localhost:{port}", "Origin": f"http://localhost:{port}"},
    )

    assert status == 200
    assert "provider" in json.loads(body)


def test_options_preflight_is_not_granted(running_server) -> None:
    status, headers, _ = _request(
        running_server,
        "OPTIONS",
        "/api/settings",
        headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "PUT"},
    )

    assert status >= 400
    assert not any(name.lower().startswith("access-control-") for name in headers)
