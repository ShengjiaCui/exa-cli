"""Unit tests for /answer body assembly (cmd_answer) + streaming."""

from __future__ import annotations

from argparse import Namespace

import pytest

from exa_cli.cli import cmd_answer


def _answer_args(query="what is x?", **overrides) -> Namespace:
    base = dict(
        command="answer", query=query,
        text=False, output_schema=None,
        stream=False, json=True, output=None, timeout=60,
    )
    base.update(overrides)
    return Namespace(**base)


class TestAnswerBasic:
    def test_query_always_sent(self, captured_request):
        cmd_answer(_answer_args(query="who founded exa?"))
        assert captured_request.body["query"] == "who founded exa?"

    def test_path_is_answer(self, captured_request):
        cmd_answer(_answer_args())
        assert captured_request.path == "/answer"

    def test_text_flag(self, captured_request):
        cmd_answer(_answer_args(text=True))
        assert captured_request.body["text"] is True

    def test_text_default_false_omitted(self, captured_request):
        cmd_answer(_answer_args(text=False))
        assert "text" not in captured_request.body


class TestAnswerOutputSchema:
    def test_output_schema_inline(self, captured_request):
        cmd_answer(_answer_args(output_schema='{"type":"object","properties":{"a":{"type":"string"}}}'))
        assert captured_request.body["outputSchema"]["properties"]["a"]["type"] == "string"

    def test_output_schema_at_file(self, captured_request, tmp_path):
        f = tmp_path / "ans-schema.json"
        f.write_text('{"type":"object","properties":{"result":{"type":"string"}}}')
        cmd_answer(_answer_args(output_schema=f"@{f}"))
        assert captured_request.body["outputSchema"]["properties"]["result"]["type"] == "string"

    def test_output_schema_none_omitted(self, captured_request):
        cmd_answer(_answer_args(output_schema=None))
        assert "outputSchema" not in captured_request.body
