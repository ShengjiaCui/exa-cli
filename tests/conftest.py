"""Shared pytest fixtures for exa-cli.

The key fixture is `captured_request`: it monkeypatches `exa_cli.client.request`
to intercept the (path, body) that would be sent to Exa, returning a canned
response. This lets us assert on the *wire-format body* without hitting the API.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture
def captured_request(monkeypatch):
    """Patch client.request to capture (path, body) and return a canned response.

    Returns a SimpleNamespace with .path, .body, .calls (list of (path, body)),
    and .response (the canned response to return, default: a minimal search ok).
    """
    state = SimpleNamespace(
        path=None, body=None, calls=[], kwargs=None,
        response={"requestId": "test-req", "results": [{"title": "T", "url": "https://example.com", "score": 0.5}]},
    )

    def fake_request(path: str, body: dict, **kwargs: Any):
        state.path = path
        state.body = body
        state.kwargs = kwargs
        state.calls.append((path, body))
        return state.response

    monkeypatch.setattr("exa_cli.client.request", fake_request)
    return state


@pytest.fixture
def captured_stream(monkeypatch):
    """Patch client.request_stream to capture the body and yield canned events."""
    state = SimpleNamespace(path=None, body=None, events=[
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {"content": " world"}}]},
        {"citations": [{"title": "S1", "url": "https://s1.com"}]},
    ])

    def fake_stream(path: str, body: dict, **kwargs: Any):
        state.path = path
        state.body = body
        yield from state.events

    monkeypatch.setattr("exa_cli.client.request_stream", fake_stream)
    return state
