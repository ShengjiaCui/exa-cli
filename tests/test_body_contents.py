"""Unit tests for /contents body assembly (cmd_contents).

Key difference from /search: content params are TOP-LEVEL, not nested under contents.
"""

from __future__ import annotations

from argparse import Namespace

import pytest

from exa_cli.cli import cmd_contents


def _contents_args(urls=None, **overrides) -> Namespace:
    base = dict(
        command="contents", urls=urls or ["https://example.com"],
        text=False, highlights=False, summary=False,
        text_max_chars=None, text_include_html=False, text_verbosity=None,
        text_include_sections=None, text_exclude_sections=None,
        highlights_query=None, highlights_max_chars=None,
        summary_query=None, summary_schema=None,
        max_age_hours=None, livecrawl_timeout=None,
        subpages=None, subpage_target=None,
        extras_links=None, extras_image_links=None,
        json=True, output=None, timeout=60, text_len=300,
    )
    base.update(overrides)
    return Namespace(**base)


class TestContentsBasic:
    def test_ids_from_urls(self, captured_request):
        cmd_contents(_contents_args(urls=["https://a.com", "https://b.com"]))
        assert captured_request.body["ids"] == ["https://a.com", "https://b.com"]

    def test_path_is_contents(self, captured_request):
        cmd_contents(_contents_args())
        assert captured_request.path == "/contents"


class TestContentsTopLevelParams:
    """The critical difference: /contents puts text/highlights/summary at top level."""

    def test_text_is_top_level_not_nested(self, captured_request):
        cmd_contents(_contents_args(text=True))
        assert captured_request.body["text"] is True
        assert "contents" not in captured_request.body

    def test_text_max_chars_is_top_level_object(self, captured_request):
        cmd_contents(_contents_args(text=True, text_max_chars=500))
        assert captured_request.body["text"] == {"maxCharacters": 500}

    def test_highlights_is_top_level(self, captured_request):
        cmd_contents(_contents_args(highlights=True, highlights_query="q"))
        assert captured_request.body["highlights"] == {"query": "q"}

    def test_summary_is_top_level(self, captured_request):
        cmd_contents(_contents_args(summary=True, summary_query="sum"))
        assert captured_request.body["summary"] == {"query": "sum"}

    def test_subpages_top_level(self, captured_request):
        cmd_contents(_contents_args(subpages=5, subpage_target="docs"))
        assert captured_request.body["subpages"] == 5
        assert captured_request.body["subpageTarget"] == ["docs"]

    def test_max_age_hours_top_level(self, captured_request):
        cmd_contents(_contents_args(max_age_hours=0))
        assert captured_request.body["maxAgeHours"] == 0

    def test_extras_top_level(self, captured_request):
        cmd_contents(_contents_args(extras_links=3))
        assert captured_request.body["extras"] == {"links": 3}

    def test_no_content_flags_minimal_body(self, captured_request):
        cmd_contents(_contents_args())
        # Only ids should be present, no content keys
        assert captured_request.body == {"ids": ["https://example.com"]}
