"""Unit tests for /search body assembly (cmd_search + _build_contents_object).

These tests intercept client.request and assert the wire-format body is correct:
camelCase keys, contents nesting, filter translation, etc. No real API calls.
"""

from __future__ import annotations

import json
from argparse import Namespace
from types import SimpleNamespace

import pytest

from exa_cli.cli import (
    cmd_search,
    _build_contents_object,
    _text_block,
    _highlights_block,
    _summary_block,
    _extras_block,
)
from exa_cli.client import ExaError


def _search_args(**overrides) -> Namespace:
    """Build a minimal args namespace for cmd_search with sensible defaults."""
    base = dict(
        command="search", query="test query", type="auto",
        num_results=None, category=None,
        include_domains=None, exclude_domains=None,
        start_date=None, end_date=None, start_crawl_date=None, end_crawl_date=None,
        system_prompt=None, output_schema=None, moderation=False, stream=False,
        additional_queries=None, user_location=None,
        contents=False, text=False, highlights=False, summary=False,
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


# --- cmd_search: basic body shape ---

class TestSearchBasic:
    def test_query_and_type_always_sent(self, captured_request):
        cmd_search(_search_args(query="hello", type="fast"))
        assert captured_request.body["query"] == "hello"
        assert captured_request.body["type"] == "fast"

    def test_num_results_translated_to_camelcase(self, captured_request):
        cmd_search(_search_args(num_results=5))
        assert captured_request.body["numResults"] == 5
        assert "num_results" not in captured_request.body

    def test_num_results_none_omitted(self, captured_request):
        cmd_search(_search_args(num_results=None))
        assert "numResults" not in captured_request.body

    def test_path_is_search(self, captured_request):
        cmd_search(_search_args())
        assert captured_request.path == "/search"


# --- cmd_search: filters ---

class TestSearchFilters:
    def test_include_domains_becomes_camelcase_list(self, captured_request):
        cmd_search(_search_args(include_domains="a.com,b.com"))
        assert captured_request.body["includeDomains"] == ["a.com", "b.com"]

    def test_exclude_domains_becomes_camelcase_list(self, captured_request):
        cmd_search(_search_args(exclude_domains="x.com"))
        assert captured_request.body["excludeDomains"] == ["x.com"]

    def test_start_date_becomes_published_date(self, captured_request):
        cmd_search(_search_args(start_date="2026-01-01"))
        assert captured_request.body["startPublishedDate"] == "2026-01-01"

    def test_end_date_becomes_published_date(self, captured_request):
        cmd_search(_search_args(end_date="2026-12-31"))
        assert captured_request.body["endPublishedDate"] == "2026-12-31"

    def test_crawl_date_filters(self, captured_request):
        cmd_search(_search_args(start_crawl_date="2025-06-01", end_crawl_date="2025-12-01"))
        assert captured_request.body["startCrawlDate"] == "2025-06-01"
        assert captured_request.body["endCrawlDate"] == "2025-12-01"

    def test_no_filters_no_date_keys(self, captured_request):
        cmd_search(_search_args())
        for k in ("includeDomains", "excludeDomains", "startPublishedDate", "endPublishedDate", "startCrawlDate", "endCrawlDate"):
            assert k not in captured_request.body

    def test_domain_path_prefix_and_wildcard_preserved(self, captured_request):
        cmd_search(_search_args(include_domains="exa.ai/blog,*.substack.com"))
        assert captured_request.body["includeDomains"] == ["exa.ai/blog", "*.substack.com"]


# --- cmd_search: deep-search params ---

class TestSearchDeepParams:
    def test_system_prompt(self, captured_request):
        cmd_search(_search_args(system_prompt="be concise"))
        assert captured_request.body["systemPrompt"] == "be concise"

    def test_moderation_flag(self, captured_request):
        cmd_search(_search_args(moderation=True))
        assert captured_request.body["moderation"] is True

    def test_additional_queries_csv(self, captured_request):
        cmd_search(_search_args(additional_queries="q1,q2"))
        assert captured_request.body["additionalQueries"] == ["q1", "q2"]

    def test_user_location(self, captured_request):
        cmd_search(_search_args(user_location="US"))
        assert captured_request.body["userLocation"] == "US"

    def test_output_schema_inline(self, captured_request):
        cmd_search(_search_args(output_schema='{"type":"object","properties":{"a":{"type":"string"}}}'))
        assert captured_request.body["outputSchema"]["type"] == "object"

    def test_output_schema_none_omitted(self, captured_request):
        cmd_search(_search_args(output_schema=None))
        assert "outputSchema" not in captured_request.body


# --- cmd_search: contents nesting ---

class TestSearchContentsNesting:
    def test_contents_flag_false_omits_contents_key(self, captured_request):
        cmd_search(_search_args(contents=False))
        assert "contents" not in captured_request.body

    def test_text_flag_without_contents_omitted(self, captured_request):
        # --text without --contents should not produce contents block
        cmd_search(_search_args(contents=False, text=True))
        assert "contents" not in captured_request.body

    def test_text_with_contents_nests_text(self, captured_request):
        cmd_search(_search_args(contents=True, text=True))
        assert captured_request.body["contents"]["text"] is True

    def test_text_max_chars_nests_in_text_object(self, captured_request):
        cmd_search(_search_args(contents=True, text=True, text_max_chars=1000))
        assert captured_request.body["contents"]["text"] == {"maxCharacters": 1000}

    def test_text_include_html(self, captured_request):
        cmd_search(_search_args(contents=True, text=True, text_include_html=True))
        assert captured_request.body["contents"]["text"]["includeHtmlTags"] is True

    def test_text_verbosity(self, captured_request):
        cmd_search(_search_args(contents=True, text=True, text_verbosity="compact"))
        assert captured_request.body["contents"]["text"]["verbosity"] == "compact"

    def test_text_sections_split(self, captured_request):
        cmd_search(_search_args(contents=True, text=True,
                                text_include_sections="body,header",
                                text_exclude_sections="footer,nav"))
        assert captured_request.body["contents"]["text"]["includeSections"] == ["body", "header"]
        assert captured_request.body["contents"]["text"]["excludeSections"] == ["footer", "nav"]

    def test_highlights_with_query(self, captured_request):
        cmd_search(_search_args(contents=True, highlights=True, highlights_query="funding"))
        assert captured_request.body["contents"]["highlights"] == {"query": "funding"}

    def test_summary_with_query_and_schema(self, captured_request, tmp_path):
        schema_file = tmp_path / "s.json"
        schema_file.write_text('{"type":"object"}')
        cmd_search(_search_args(contents=True, summary=True,
                                summary_query="extract info",
                                summary_schema=f"@{schema_file}"))
        assert captured_request.body["contents"]["summary"] == {
            "query": "extract info", "schema": {"type": "object"}
        }

    def test_subpages_nests_in_contents(self, captured_request):
        cmd_search(_search_args(contents=True, text=True, subpages=3, subpage_target="docs,about"))
        assert captured_request.body["contents"]["subpages"] == 3
        assert captured_request.body["contents"]["subpageTarget"] == ["docs", "about"]

    def test_max_age_hours_nests_in_contents(self, captured_request):
        cmd_search(_search_args(contents=True, text=True, max_age_hours=0))
        assert captured_request.body["contents"]["maxAgeHours"] == 0

    def test_livecrawl_timeout_nests_in_contents(self, captured_request):
        cmd_search(_search_args(contents=True, text=True, livecrawl_timeout=5000))
        assert captured_request.body["contents"]["livecrawlTimeout"] == 5000

    def test_extras_nests_in_contents(self, captured_request):
        cmd_search(_search_args(contents=True, text=True, extras_links=5, extras_image_links=2))
        assert captured_request.body["contents"]["extras"] == {"links": 5, "imageLinks": 2}


# --- _build_contents_object: direct unit tests ---

class TestBuildContentsObject:
    def test_no_content_flags_returns_none(self):
        args = _search_args()
        assert _build_contents_object(args) is None

    def test_text_only(self):
        args = _search_args(text=True)
        assert _build_contents_object(args) == {"text": True}

    def test_all_content_types(self):
        args = _search_args(text=True, highlights=True, summary=True,
                            max_age_hours=24, subpages=2)
        block = _build_contents_object(args)
        assert "text" in block
        assert "highlights" in block
        assert "summary" in block
        assert block["maxAgeHours"] == 24
        assert block["subpages"] == 2
