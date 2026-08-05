"""Unit tests for client.py: auth, error normalization, stream delegation.

These mock urllib.request.urlopen to avoid real HTTP. They verify that
ExaError is raised correctly and that the Authorization header is set.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch, MagicMock
import urllib.error

import pytest

from exa_cli import client
from exa_cli.client import ExaError, request, _api_key, BASE_URL


class TestApiKey:
    def test_present(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "test-key-123")
        assert _api_key() == "test-key-123"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "  test-key  ")
        assert _api_key() == "test-key"

    def test_missing_raises(self, monkeypatch):
        monkeypatch.delenv("EXA_API_KEY", raising=False)
        with pytest.raises(ExaError, match="EXA_API_KEY is not set"):
            _api_key()

    def test_empty_raises(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "")
        with pytest.raises(ExaError, match="EXA_API_KEY is not set"):
            _api_key()


class TestRequestAuth:
    def _mock_response(self, data):
        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode("utf-8")
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_authorization_header_bearer(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "my-secret")
        resp = self._mock_response({"ok": True})
        with patch("urllib.request.urlopen", return_value=resp) as m:
            request("/search", {"query": "x"})
            req_obj = m.call_args[0][0]
            assert req_obj.headers.get("Authorization") == "Bearer my-secret"

    def test_content_type_header(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "k")
        resp = self._mock_response({"ok": True})
        with patch("urllib.request.urlopen", return_value=resp) as m:
            request("/search", {"query": "x"})
            req_obj = m.call_args[0][0]
            assert req_obj.headers.get("Content-type") == "application/json"

    def test_url_construction(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "k")
        resp = self._mock_response({"ok": True})
        with patch("urllib.request.urlopen", return_value=resp) as m:
            request("/contents", {"ids": ["x"]})
            req_obj = m.call_args[0][0]
            assert req_obj.full_url == f"{BASE_URL}/contents"

    def test_post_method(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "k")
        resp = self._mock_response({"ok": True})
        with patch("urllib.request.urlopen", return_value=resp) as m:
            request("/search", {"query": "x"})
            req_obj = m.call_args[0][0]
            assert req_obj.method == "POST"

    def test_body_json_encoded(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "k")
        resp = self._mock_response({"ok": True})
        with patch("urllib.request.urlopen", return_value=resp) as m:
            request("/search", {"query": "test", "numResults": 5})
            req_obj = m.call_args[0][0]
            sent = json.loads(req_obj.data.decode("utf-8"))
            assert sent == {"query": "test", "numResults": 5}

    def test_returns_parsed_json(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "k")
        resp = self._mock_response({"results": [1, 2, 3]})
        with patch("urllib.request.urlopen", return_value=resp):
            result = request("/search", {"query": "x"})
            assert result == {"results": [1, 2, 3]}


class TestRequestErrors:
    def test_http_error_normalized_to_exa_error(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "k")
        err_body = json.dumps({"message": "Invalid query"}).encode("utf-8")
        http_err = urllib.error.HTTPError(
            "https://api.exa.ai/search", 400, "Bad Request",
            {}, io.BytesIO(err_body)
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(ExaError) as exc_info:
                request("/search", {"query": "x"})
            assert exc_info.value.status == 400
            assert "Invalid query" in str(exc_info.value)

    def test_http_error_401(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "bad-key")
        http_err = urllib.error.HTTPError(
            "https://api.exa.ai/search", 401, "Unauthorized",
            {}, io.BytesIO(b'{"error": "invalid api key"}')
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(ExaError) as exc_info:
                request("/search", {"query": "x"})
            assert exc_info.value.status == 401

    def test_network_error_normalized(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "k")
        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("connection refused")):
            with pytest.raises(ExaError, match="network error"):
                request("/search", {"query": "x"})


class TestStreamDelegation:
    def test_stream_true_delegates_to_request_stream(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "k")
        called = {}

        def fake_stream(path, body, **kwargs):
            called["path"] = path
            called["body"] = body
            yield {"choices": [{"delta": {"content": "x"}}]}

        monkeypatch.setattr("exa_cli.client._request_stream", fake_stream)
        gen = request("/search", {"query": "x"}, stream=True)
        # Must consume the generator — _request_stream is lazy, so the fake only
        # records `called` when iteration begins.
        events = list(gen)
        assert called["path"] == "/search"
        assert events[0]["choices"][0]["delta"]["content"] == "x"
