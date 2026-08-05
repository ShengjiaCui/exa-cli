"""Thin HTTP client for the Exa.ai API.

All wire-format parameters use camelCase per Exa's HTTP API convention
(the Python SDK uses snake_case; raw HTTP does not). See
https://exa.ai/docs/reference/search-api-guide-for-coding-agents

Only Authorization: Bearer is used (no x-api-key) to match the documented cURL
examples. Errors are surfaced as ExaError with the upstream message + status.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "https://api.exa.ai"
DEFAULT_TIMEOUT = 60  # seconds; /answer can be slow, /search with deep types too


class ExaError(Exception):
    """Raised on any Exa API or client error. Message includes status + body."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        self.status = status
        self.body = body
        detail = message
        if status is not None:
            detail = f"[HTTP {status}] {message}"
        super().__init__(detail)


def _api_key() -> str:
    key = os.environ.get("EXA_API_KEY", "").strip()
    if not key:
        raise ExaError(
            "EXA_API_KEY is not set. Export it or inject via "
            "`launchctl setenv EXA_API_KEY <key>`. Get one at https://exa.ai/dashboard."
        )
    return key


def request(path: str, body: dict[str, Any], *, timeout: int = DEFAULT_TIMEOUT, stream: bool = False) -> Any:
    """POST JSON to BASE_URL+path with bearer auth, return parsed JSON.

    The caller is responsible for shaping `body` with camelCase keys; this
    function only handles transport, auth, and error normalization.

    If `stream=True`, the body gets `"stream": true` injected and a generator
    yielding parsed SSE events is returned instead of a parsed JSON object.
    """
    if stream:
        # Inject stream:true and hand off to the streaming reader.
        return _request_stream(path, body, timeout=timeout)

    url = f"{BASE_URL}{path}"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key()}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        # Surface Exa's error envelope if present, else the raw body.
        try:
            parsed = json.loads(err_body)
            msg = parsed.get("message") or parsed.get("error") or err_body
        except Exception:
            msg = err_body or e.reason
        raise ExaError(msg, status=e.code, body=err_body) from None
    except urllib.error.URLError as e:
        raise ExaError(f"network error: {e.reason}") from None

    if not raw:
        return None
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ExaError(f"response was not valid JSON: {e}") from None

    # Report cost to exa-rotator daemon (fire-and-forget, failures silent).
    # Exa includes costDollars.total in /search and /answer responses; the rotator
    # accumulates this to decide key rotation. If the daemon isn't running, skip.
    _report_cost(result)
    return result


# exa-rotator daemon endpoint (loopback, fire-and-forget).
_ROTATOR_URL = "http://127.0.0.1:8732/api/ingest-cost"


def _report_cost(result: Any) -> None:
    """POST costDollars to the local exa-rotator daemon. Silent on failure."""
    if not isinstance(result, dict):
        return
    cost = result.get("costDollars")
    if not isinstance(cost, dict) or "total" not in cost:
        return
    payload = json.dumps({
        "cost_dollars": cost["total"],
        "request_id": result.get("requestId"),
    }).encode("utf-8")
    req = urllib.request.Request(_ROTATOR_URL, data=payload, method="POST",
                                headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=2)  # 2s timeout, don't block the CLI
    except Exception:
        pass  # daemon down / not installed — silently skip


def _request_stream(path: str, body: dict[str, Any], *, timeout: int = DEFAULT_TIMEOUT) -> Any:
    """POST with stream:true — yields parsed SSE events (server-sent events).

    Each yielded value is a dict (one SSE `data:` payload). The final event from
    /answer carries the citations + costDollars; intermediate events carry
    OpenAI-compatible completion chunks with incremental answer text.
    """
    url = f"{BASE_URL}{path}"
    payload = json.dumps({**body, "stream": True}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key()}",
            "Accept": "text/event-stream",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise ExaError(err_body or e.reason, status=e.code, body=err_body) from None
    except urllib.error.URLError as e:
        raise ExaError(f"network error: {e.reason}") from None

    with resp:
        for line in resp:
            line = line.decode("utf-8", errors="replace").rstrip("\n")
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                # Non-JSON keepalive/comment — skip.
                continue


# Public alias retained for direct callers (e.g. answer --stream).
request_stream = _request_stream
