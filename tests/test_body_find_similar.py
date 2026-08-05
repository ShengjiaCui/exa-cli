"""Unit tests for /findSimilar body assembly (cmd_find_similar)."""

from __future__ import annotations

from argparse import Namespace

import pytest

from exa_cli.cli import cmd_find_similar


def _fs_args(url="https://example.com", **overrides) -> Namespace:
    base = dict(
        command="find-similar", url=url,
        num_results=None, category=None,
        include_domains=None, exclude_domains=None,
        start_date=None, end_date=None, start_crawl_date=None, end_crawl_date=None,
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


class TestFindSimilarBasic:
    def test_url_always_sent(self, captured_request):
        cmd_find_similar(_fs_args(url="https://target.com"))
        assert captured_request.body["url"] == "https://target.com"

    def test_path_is_findSimilar(self, captured_request):
        cmd_find_similar(_fs_args())
        assert captured_request.path == "/findSimilar"

    def test_num_results_camelcase(self, captured_request):
        cmd_find_similar(_fs_args(num_results=10))
        assert captured_request.body["numResults"] == 10


class TestFindSimilarFilters:
    def test_include_domains(self, captured_request):
        cmd_find_similar(_fs_args(include_domains="a.com,b.com"))
        assert captured_request.body["includeDomains"] == ["a.com", "b.com"]

    def test_exclude_domains(self, captured_request):
        cmd_find_similar(_fs_args(exclude_domains="source.com"))
        assert captured_request.body["excludeDomains"] == ["source.com"]

    def test_category(self, captured_request):
        cmd_find_similar(_fs_args(category="research paper"))
        assert captured_request.body["category"] == "research paper"

    def test_date_filters(self, captured_request):
        cmd_find_similar(_fs_args(start_date="2026-01-01", end_date="2026-06-01"))
        assert captured_request.body["startPublishedDate"] == "2026-01-01"
        assert captured_request.body["endPublishedDate"] == "2026-06-01"


class TestFindSimilarContents:
    def test_contents_nests_like_search(self, captured_request):
        cmd_find_similar(_fs_args(contents=True, text=True, text_max_chars=500))
        assert captured_request.body["contents"]["text"] == {"maxCharacters": 500}

    def test_contents_false_omits_contents(self, captured_request):
        cmd_find_similar(_fs_args(contents=False, text=True))
        assert "contents" not in captured_request.body
