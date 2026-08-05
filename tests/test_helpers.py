"""Unit tests for CLI helper functions: _split_csv, _load_json_file, _resolve_schema."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from exa_cli.cli import _split_csv, _load_json_file, _resolve_schema


# --- _split_csv ---

class TestSplitCsv:
    def test_none_returns_none(self):
        assert _split_csv(None) is None

    def test_empty_returns_none(self):
        assert _split_csv("") is None

    def test_single(self):
        assert _split_csv("a.com") == ["a.com"]

    def test_multiple(self):
        assert _split_csv("a.com,b.com,c.com") == ["a.com", "b.com", "c.com"]

    def test_strips_whitespace(self):
        assert _split_csv(" a.com , b.com ,c.com") == ["a.com", "b.com", "c.com"]

    def test_drops_empty_parts(self):
        assert _split_csv("a.com,,b.com,") == ["a.com", "b.com"]

    def test_path_prefix_preserved(self):
        assert _split_csv("exa.ai/blog,*.substack.com") == ["exa.ai/blog", "*.substack.com"]


# --- _load_json_file ---

class TestLoadJsonFile:
    def test_none_returns_none(self):
        assert _load_json_file(None) is None

    def test_empty_string_returns_none(self):
        assert _load_json_file("") is None

    def test_nonexistent_file_returns_none(self, tmp_path):
        assert _load_json_file(str(tmp_path / "nope.json")) is None

    def test_loads_valid_json(self, tmp_path):
        f = tmp_path / "schema.json"
        f.write_text('{"type": "object", "properties": {"a": {"type": "string"}}}')
        result = _load_json_file(str(f))
        assert result == {"type": "object", "properties": {"a": {"type": "string"}}}

    def test_directory_returns_none(self, tmp_path):
        # os.path.isfile is False for directories
        assert _load_json_file(str(tmp_path)) is None


# --- _resolve_schema ---

class TestResolveSchema:
    def test_none_returns_none(self):
        assert _resolve_schema(None) is None

    def test_at_file_loads_json(self, tmp_path):
        f = tmp_path / "s.json"
        f.write_text('{"type": "object"}')
        assert _resolve_schema(f"@{f}") == {"type": "object"}

    def test_at_file_missing_raises_systemexit(self):
        with pytest.raises(SystemExit, match="schema file not found"):
            _resolve_schema("@/nonexistent/path/schema.json")

    def test_inline_json_object(self):
        result = _resolve_schema('{"type": "string"}')
        assert result == {"type": "string"}

    def test_inline_json_array(self):
        result = _resolve_schema('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_inline_json_with_whitespace(self):
        result = _resolve_schema('  {"type": "string"}  ')
        assert result == {"type": "string"}

    def test_invalid_inline_json_raises_systemexit(self):
        with pytest.raises(SystemExit, match="invalid inline JSON"):
            _resolve_schema('{"broken": }')

    def test_plain_string_passthrough(self):
        # A value that isn't @file, doesn't start with { or [, passes through as-is.
        assert _resolve_schema("just-a-string") == "just-a-string"
