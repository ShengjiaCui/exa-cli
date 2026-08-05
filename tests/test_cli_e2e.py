"""Integration tests for the CLI entry point: argparse, stdin, exit codes.

These test main() directly (no subprocess) to keep them fast. They verify
the command-line interface parses correctly and errors propagate as exit codes.
"""

from __future__ import annotations

import sys
from io import StringIO

import pytest

from exa_cli.cli import main, build_parser


class TestArgparse:
    def test_help_search_lists_subcommands(self):
        parser = build_parser()
        # argparse prints to stdout on --help and exits 0
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_no_command_errors(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args([])
        # required subcommand → exit 2
        assert exc_info.value.code == 2

    def test_search_requires_query_when_not_stdin(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        monkeypatch.setattr("exa_cli.client.request", lambda *a, **k: {"results": []})
        with pytest.raises(SystemExit):
            # query is optional (nargs='?') but if absent + not '-', main() should error
            main(["search"])

    def test_search_reads_query_from_stdin(self, monkeypatch, captured_request):
        monkeypatch.setattr("sys.stdin", StringIO("query from stdin"))
        main(["search", "-", "--json"])
        assert captured_request.body["query"] == "query from stdin"

    def test_answer_reads_query_from_stdin(self, monkeypatch, captured_request):
        monkeypatch.setattr("sys.stdin", StringIO("stdin question"))
        main(["answer", "-", "--json"])
        assert captured_request.body["query"] == "stdin question"

    def test_unknown_flag_errors(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["search", "x", "--nonexistent-flag"])
        assert exc_info.value.code == 2

    def test_unknown_subcommand_errors(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["frobnicate", "x"])
        assert exc_info.value.code == 2


class TestExitCodes:
    def test_missing_key_exits_1(self, monkeypatch, capsys):
        monkeypatch.delenv("EXA_API_KEY", raising=False)
        # Also clear launchctl fallback by patching
        monkeypatch.setattr("exa_cli.client._api_key",
                            lambda: (_ for _ in ()).throw(
                                __import__("exa_cli.client", fromlist=["ExaError"]).ExaError("no key")))
        code = main(["search", "test", "--json"])
        assert code == 1
        err = capsys.readouterr().err
        assert "exa:" in err.lower()

    def test_api_error_exits_1(self, monkeypatch, capsys):
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        from exa_cli.client import ExaError

        def fail(*a, **k):
            raise ExaError("[HTTP 500] boom", status=500)
        monkeypatch.setattr("exa_cli.client.request", fail)
        code = main(["search", "test", "--json"])
        assert code == 1

    def test_keyboard_interrupt_exits_130(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "test-key")

        def fail(*a, **k):
            raise KeyboardInterrupt
        monkeypatch.setattr("exa_cli.client.request", fail)
        code = main(["search", "test", "--json"])
        assert code == 130


class TestSubcommandRouting:
    def test_search_routes_correctly(self, monkeypatch, captured_request):
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        main(["search", "my query", "--num-results", "3", "--json"])
        assert captured_request.path == "/search"
        assert captured_request.body["query"] == "my query"
        assert captured_request.body["numResults"] == 3

    def test_contents_routes_correctly(self, monkeypatch, captured_request):
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        main(["contents", "https://a.com", "https://b.com", "--text", "--json"])
        assert captured_request.path == "/contents"
        assert captured_request.body["ids"] == ["https://a.com", "https://b.com"]
        assert captured_request.body["text"] is True

    def test_find_similar_routes_correctly(self, monkeypatch, captured_request):
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        main(["find-similar", "https://seed.com", "--num-results", "5", "--json"])
        assert captured_request.path == "/findSimilar"
        assert captured_request.body["url"] == "https://seed.com"

    def test_answer_routes_correctly(self, monkeypatch, captured_request):
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        main(["answer", "what is x?", "--json"])
        assert captured_request.path == "/answer"
        assert captured_request.body["query"] == "what is x?"
