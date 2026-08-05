"""exa-cli entry point.

Subcommands mirror the four Exa endpoints and are designed to feel like `tvly`:
  exa search         -> POST /search
  exa contents       -> POST /contents
  exa find-similar   -> POST /findSimilar
  exa answer         -> POST /answer

Every subcommand supports --json (machine-readable, for agents/skills) and
-o FILE (save output). Authentication is via the EXA_API_KEY environment variable.

Wire format: Exa's HTTP API uses camelCase; this CLI accepts kebab/case CLI flags
and builds the camelCase JSON body internally. Content params on /search and
/findSimilar are nested under `contents`; on /contents they are top-level.
Reference: https://exa.ai/docs/reference/search-api-guide-for-coding-agents
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from . import __version__
from . import client


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _emit(data: Any, *, json_mode: bool, out_path: str | None, human_fn) -> None:
    """Centralize --json / -o / human rendering. `human_fn` renders the default view."""
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n" if json_mode else human_fn(data)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        sys.stderr.write(f"Saved to {out_path}\n")
    else:
        sys.stdout.write(text)


def _truncate(s: Any, n: int = 300) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[:n].rstrip() + "…"


# ---------------------------------------------------------------------------
# Shared parsing helpers
# ---------------------------------------------------------------------------

def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


def _load_json_file(path: str | None) -> Any:
    """Load JSON from a file path (for @file references).

    Returns None if the path doesn't exist or isn't a file (so callers can fall
    back to treating the value as inline JSON via _resolve_schema).
    """
    if not path:
        return None
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_schema(raw: str | None) -> Any:
    """Resolve a schema argument: @file path, inline JSON, or passthrough string.

    Order: @file → inline JSON ({...} or [...]) → raw string. Used for
    --output-schema and --summary-schema.
    """
    if raw is None:
        return None
    if raw.startswith("@"):
        loaded = _load_json_file(raw[1:])
        if loaded is not None:
            return loaded
        raise SystemExit(f"exa: schema file not found: {raw[1:]}")
    stripped = raw.strip()
    if stripped and stripped[0] in "{[":
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as e:
            raise SystemExit(f"exa: invalid inline JSON schema: {e}") from None
    return raw


def _text_block(args, *, prefix: str = "") -> dict[str, Any] | bool:
    """Build the `text` sub-object (or True) from --text* flags.

    Supports: --text (enable), --text-max-chars, --text-include-html,
    --text-verbosity, --text-include-sections, --text-exclude-sections.
    `prefix` allows reusing for --highlights/--summary where applicable.
    """
    enabled = getattr(args, f"{prefix}text", False) if prefix else getattr(args, "text", False)
    if not enabled:
        return None
    obj: dict[str, Any] = {}
    maxc = getattr(args, f"{prefix}text_max_chars", None) if prefix else getattr(args, "text_max_chars", None)
    html = getattr(args, f"{prefix}text_include_html", False) if prefix else getattr(args, "text_include_html", False)
    verb = getattr(args, f"{prefix}text_verbosity", None) if prefix else getattr(args, "text_verbosity", None)
    inc_s = getattr(args, f"{prefix}text_include_sections", None) if prefix else getattr(args, "text_include_sections", None)
    exc_s = getattr(args, f"{prefix}text_exclude_sections", None) if prefix else getattr(args, "text_exclude_sections", None)
    if maxc is not None:
        obj["maxCharacters"] = maxc
    if html:
        obj["includeHtmlTags"] = True
    if verb:
        obj["verbosity"] = verb
    if inc_s:
        obj["includeSections"] = _split_csv(inc_s)
    if exc_s:
        obj["excludeSections"] = _split_csv(exc_s)
    return obj if obj else True


def _highlights_block(args) -> dict[str, Any] | bool:
    """Build the `highlights` sub-object. Supports --highlights-query, --highlights-max-chars."""
    if not getattr(args, "highlights", False):
        return None
    obj: dict[str, Any] = {}
    q = getattr(args, "highlights_query", None)
    maxc = getattr(args, "highlights_max_chars", None)
    if q:
        obj["query"] = q
    if maxc is not None:
        obj["maxCharacters"] = maxc
    return obj if obj else True


def _summary_block(args) -> dict[str, Any] | bool:
    """Build the `summary` sub-object. Supports --summary-query, --summary-schema."""
    if not getattr(args, "summary", False):
        return None
    obj: dict[str, Any] = {}
    q = getattr(args, "summary_query", None)
    schema = getattr(args, "summary_schema", None)
    if q:
        obj["query"] = q
    if schema:
        obj["schema"] = _resolve_schema(schema)
    return obj if obj else True


def _extras_block(args) -> dict[str, Any] | None:
    """Build the `extras` sub-object. Supports --extras-links, --extras-image-links."""
    obj: dict[str, Any] = {}
    links = getattr(args, "extras_links", None)
    imgs = getattr(args, "extras_image_links", None)
    if links is not None:
        obj["links"] = links
    if imgs is not None:
        obj["imageLinks"] = imgs
    return obj if obj else None


def _build_contents_object(args) -> dict[str, Any] | None:
    """Assemble the full nested `contents` object from all content flags.

    Used by /search and /findSimilar. Returns None if no content flags are set.
    """
    block: dict[str, Any] = {}
    t = _text_block(args)
    if t is not None:
        block["text"] = t
    h = _highlights_block(args)
    if h is not None:
        block["highlights"] = h
    s = _summary_block(args)
    if s is not None:
        block["summary"] = s
    # livecrawl control
    if getattr(args, "max_age_hours", None) is not None:
        block["maxAgeHours"] = args.max_age_hours
    if getattr(args, "livecrawl_timeout", None) is not None:
        block["livecrawlTimeout"] = args.livecrawl_timeout
    # subpages
    sp = getattr(args, "subpages", None)
    if sp is not None:
        block["subpages"] = sp
    spt = getattr(args, "subpage_target", None)
    if spt:
        block["subpageTarget"] = _split_csv(spt) or [spt]
    # extras
    e = _extras_block(args)
    if e:
        block["extras"] = e
    return block if block else None


def _common_search_filter_args(p: argparse.ArgumentParser) -> None:
    """Domain/date filters shared by /search and /findSimilar."""
    p.add_argument("--include-domains", default=None, metavar="CSV",
                   help="Comma-separated domains to include (supports path prefixes like exa.ai/blog, wildcards *.substack.com).")
    p.add_argument("--exclude-domains", default=None, metavar="CSV", help="Comma-separated domains to exclude.")
    p.add_argument("--start-date", default=None, metavar="YYYY-MM-DD", help="Results published on/after this date.")
    p.add_argument("--end-date", default=None, metavar="YYYY-MM-DD", help="Results published on/before this date.")
    p.add_argument("--start-crawl-date", default=None, metavar="YYYY-MM-DD", help="Results crawled on/after this date.")
    p.add_argument("--end-crawl-date", default=None, metavar="YYYY-MM-DD", help="Results crawled on/before this date.")


def _content_selection_args(p: argparse.ArgumentParser) -> None:
    """All content-retrieval flags. Shared across search/find-similar/contents."""
    # Top-level content toggles
    p.add_argument("--text", action="store_true", help="Include full page text (clean markdown).")
    p.add_argument("--highlights", action="store_true", help="Include dense highlights (token-efficient).")
    p.add_argument("--summary", action="store_true", help="Include an AI summary.")
    # text options
    p.add_argument("--text-max-chars", type=int, default=None, metavar="N", help="Max characters of returned text.")
    p.add_argument("--text-include-html", action="store_true", help="Preserve HTML tags in text output.")
    p.add_argument("--text-verbosity", default=None, choices=["compact", "standard", "full"], help="Text verbosity level.")
    p.add_argument("--text-include-sections", default=None, metavar="CSV", help="Restrict text to sections (e.g. body,header).")
    p.add_argument("--text-exclude-sections", default=None, metavar="CSV", help="Exclude sections from text.")
    # highlights options
    p.add_argument("--highlights-query", default=None, metavar="Q", help="Query guiding which excerpts are selected.")
    p.add_argument("--highlights-max-chars", type=int, default=None, metavar="N", help="Max characters of highlights per URL.")
    # summary options
    p.add_argument("--summary-query", default=None, metavar="Q", help="Query guiding the summary.")
    p.add_argument("--summary-schema", default=None, metavar="FILE|JSON", help="JSON schema file (@path) or inline JSON for structured summary.")
    # livecrawl / freshness
    p.add_argument("--max-age-hours", type=int, default=None, metavar="H",
                   help="Max age of cached content in hours. 0 = force livecrawl, -1 = never livecrawl.")
    p.add_argument("--livecrawl-timeout", type=int, default=None, metavar="MS", help="Livecrawl timeout in milliseconds (default: 10000).")
    # subpages
    p.add_argument("--subpages", type=int, default=None, metavar="N", help="Number of subpages to crawl per result.")
    p.add_argument("--subpage-target", default=None, metavar="CSV|STR", help="Keywords/patterns to prioritize subpages (e.g. docs,about).")
    # extras
    p.add_argument("--extras-links", type=int, default=None, metavar="N", help="Number of URLs to extract from each page.")
    p.add_argument("--extras-image-links", type=int, default=None, metavar="N", help="Number of image URLs to extract from each page.")
    # human-mode render truncation
    p.add_argument("--text-len", type=int, default=300, metavar="N", help="Max chars of text/highlights to show in human mode (default: 300).")


def _apply_filters(body: dict[str, Any], args) -> None:
    """Apply domain/date filters to a body dict (in-place)."""
    inc = _split_csv(getattr(args, "include_domains", None))
    exc = _split_csv(getattr(args, "exclude_domains", None))
    if inc:
        body["includeDomains"] = inc
    if exc:
        body["excludeDomains"] = exc
    for cli_key, wire_key in [("start_date", "startPublishedDate"), ("end_date", "endPublishedDate"),
                              ("start_crawl_date", "startCrawlDate"), ("end_crawl_date", "endCrawlDate")]:
        val = getattr(args, cli_key, None)
        if val:
            body[wire_key] = val


# ---------------------------------------------------------------------------
# Subcommand: search  (POST /search)
# ---------------------------------------------------------------------------

def cmd_search(args) -> int:
    body: dict[str, Any] = {"query": args.query, "type": args.type}
    if args.num_results is not None:
        body["numResults"] = args.num_results
    if args.category:
        body["category"] = args.category
    _apply_filters(body, args)
    if args.system_prompt:
        body["systemPrompt"] = args.system_prompt
    if args.output_schema:
        body["outputSchema"] = _resolve_schema(args.output_schema)
    if args.moderation:
        body["moderation"] = True
    if args.additional_queries:
        body["additionalQueries"] = _split_csv(args.additional_queries)
    if args.user_location:
        body["userLocation"] = args.user_location
    # On /search, content retrieval is opt-in via --contents. Without it, no
    # contents block is built even if individual --text/--highlights flags are set.
    if getattr(args, "contents", False):
        contents = _build_contents_object(args)
        if contents:
            body["contents"] = contents

    # Streaming path for deep-search variants: emit incremental chunks to stdout.
    if getattr(args, "stream", False) and not args.json:
        for event in client.request("/search", body, timeout=args.timeout, stream=True):
            # OpenAI-compatible completion chunks carry the incremental text.
            choices = event.get("choices")
            if isinstance(choices, list) and choices:
                delta = choices[0].get("delta", {}).get("content")
                if delta:
                    sys.stdout.write(delta)
                    sys.stdout.flush()
        sys.stdout.write("\n")
        return 0

    data = client.request("/search", body, timeout=args.timeout)

    def human(d: Any) -> str:
        results = d.get("results", []) if isinstance(d, dict) else []
        if not results:
            return "No results.\n"
        lines = [f"{len(results)} result(s) for: {args.query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title') or '(untitled)'}")
            lines.append(f"   {r.get('url', '')}")
            if r.get("score") is not None:
                lines.append(f"   score: {r['score']}")
            if r.get("publishedDate"):
                lines.append(f"   published: {r['publishedDate']}")
            if r.get("text"):
                lines.append(f"   {_truncate(r['text'], args.text_len)}")
            if r.get("highlights"):
                hl = r["highlights"]
                joined = " ".join(hl) if isinstance(hl, list) else str(hl)
                lines.append(f"   {_truncate(joined, args.text_len)}")
            if r.get("summary"):
                lines.append(f"   summary: {_truncate(r['summary'], args.text_len)}")
            if r.get("author"):
                lines.append(f"   author: {r['author']}")
            lines.append("")
        return "\n".join(lines)

    _emit(data, json_mode=args.json, out_path=args.output, human_fn=human)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: contents  (POST /contents)
# ---------------------------------------------------------------------------

def cmd_contents(args) -> int:
    # /contents takes `ids` (URLs) top-level, and content params top-level (not nested).
    body: dict[str, Any] = {"ids": args.urls}
    t = _text_block(args)
    if t is not None:
        body["text"] = t
    h = _highlights_block(args)
    if h is not None:
        body["highlights"] = h
    s = _summary_block(args)
    if s is not None:
        body["summary"] = s
    if args.max_age_hours is not None:
        body["maxAgeHours"] = args.max_age_hours
    if args.livecrawl_timeout is not None:
        body["livecrawlTimeout"] = args.livecrawl_timeout
    if args.subpages is not None:
        body["subpages"] = args.subpages
    if args.subpage_target:
        body["subpageTarget"] = _split_csv(args.subpage_target) or [args.subpage_target]
    e = _extras_block(args)
    if e:
        body["extras"] = e

    data = client.request("/contents", body, timeout=args.timeout)

    def human(d: Any) -> str:
        results = d.get("results", []) if isinstance(d, dict) else []
        if not results:
            return "No contents returned.\n"
        lines = []
        for r in results:
            lines.append(f"# {r.get('title') or '(untitled)'}")
            lines.append(f"{r.get('url','')}\n")
            if r.get("text"):
                lines.append(r["text"])
            if r.get("highlights"):
                lines.append("\n## Highlights")
                hl = r["highlights"]
                joined = "\n".join(f"- {x}" for x in hl) if isinstance(hl, list) else str(hl)
                lines.append(joined)
            if r.get("summary"):
                lines.append(f"\n## Summary\n{r['summary']}")
            lines.append("\n---\n")
        return "\n".join(lines)

    _emit(data, json_mode=args.json, out_path=args.output, human_fn=human)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: find-similar  (POST /findSimilar)
# ---------------------------------------------------------------------------

def cmd_find_similar(args) -> int:
    body: dict[str, Any] = {"url": args.url}
    if args.num_results is not None:
        body["numResults"] = args.num_results
    if args.category:
        body["category"] = args.category
    _apply_filters(body, args)
    if args.contents:
        block = _build_contents_object(args)
        if block:
            body["contents"] = block

    data = client.request("/findSimilar", body, timeout=args.timeout)

    def human(d: Any) -> str:
        results = d.get("results", []) if isinstance(d, dict) else []
        lines = [f"Pages similar to {args.url} ({len(results)} found)\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title') or '(untitled)'}")
            lines.append(f"   {r.get('url','')}")
            if r.get("score") is not None:
                lines.append(f"   score: {r['score']}")
            if r.get("text"):
                lines.append(f"   {_truncate(r['text'], args.text_len)}")
            lines.append("")
        return "\n".join(lines) if results else "No similar pages found.\n"

    _emit(data, json_mode=args.json, out_path=args.output, human_fn=human)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: answer  (POST /answer)
# ---------------------------------------------------------------------------

def cmd_answer(args) -> int:
    body: dict[str, Any] = {"query": args.query}
    if args.text:
        body["text"] = True
    if args.output_schema:
        body["outputSchema"] = _resolve_schema(args.output_schema)

    # Streaming path: print incremental tokens, then citations block.
    if args.stream and not args.json:
        print("Answer:", flush=True)
        citations: list[Any] = []
        for event in client.request_stream("/answer", body, timeout=args.timeout):
            choices = event.get("choices")
            if isinstance(choices, list) and choices:
                delta = choices[0].get("delta", {}).get("content")
                if delta:
                    sys.stdout.write(delta)
                    sys.stdout.flush()
            if event.get("citations"):
                citations = event["citations"]
        sys.stdout.write("\n\nSources:\n")
        for i, c in enumerate(citations, 1):
            print(f"{i}. {c.get('title','(untitled)')} — {c.get('url','')}")
        return 0

    data = client.request("/answer", body, timeout=args.timeout)

    def human(d: Any) -> str:
        if not isinstance(d, dict):
            return str(d)
        ans = d.get("answer", "")
        out = [f"Answer: {ans}\n", "Sources:"]
        for i, c in enumerate(d.get("citations", []), 1):
            out.append(f"{i}. {c.get('title','(untitled)')} — {c.get('url','')}")
            if c.get("publishedDate"):
                out.append(f"   published: {c['publishedDate']}")
        return "\n".join(out) + "\n"

    _emit(data, json_mode=args.json, out_path=args.output, human_fn=human)
    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _add_output_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="Emit structured JSON (for agents/piping).")
    p.add_argument("-o", "--output", metavar="FILE", help="Save output to FILE instead of stdout.")
    p.add_argument("--timeout", type=int, default=client.DEFAULT_TIMEOUT, help="HTTP timeout in seconds.")


def _add_search_extras(p: argparse.ArgumentParser) -> None:
    """Params specific to /search (not shared with find-similar)."""
    p.add_argument("--system-prompt", default=None, metavar="TEXT",
                   help="Instructions guiding search planning/synthesis for deep-search variants.")
    p.add_argument("--output-schema", default=None, metavar="FILE|JSON",
                   help="JSON schema file (@path) or inline JSON for structured output.")
    p.add_argument("--moderation", action="store_true", help="Filter unsafe content from results.")
    p.add_argument("--stream", action="store_true", help="Stream results as SSE (OpenAI-compatible chunks).")
    p.add_argument("--additional-queries", default=None, metavar="CSV",
                   help="Extra query variations for deep-search variants.")
    p.add_argument("--user-location", default=None, metavar="CC",
                   help="Two-letter ISO country code for region bias.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="exa",
        description="Thin CLI for the Exa.ai search API. Reads EXA_API_KEY from the environment. "
                    "Symmetric to `tvly` for Tavily. Full parameter coverage of all 4 endpoints.",
    )
    parser.add_argument("--version", action="version", version=f"exa-cli {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    # search -----------------------------------------------------------------
    ps = sub.add_parser("search", help="POST /search — semantic/keyword web search.",
                        description="Search the web via Exa. Use --text/--highlights/--summary to pull content in one call.")
    ps.add_argument("query", nargs="?", help="Search query. Use '-' to read from stdin.")
    ps.add_argument("--type", default="auto",
                    choices=["auto", "instant", "fast", "deep-lite", "deep", "deep-reasoning"],
                    help="Search latency/depth profile (default: auto).")
    ps.add_argument("-n", "--num-results", type=int, default=None, help="Number of results, 1-100 (default: 10).")
    ps.add_argument("--category", default=None,
                    choices=["company", "people", "publication", "news", "personal site", "financial report", "research paper", "pdf"],
                    help="Restrict to a category index.")
    _common_search_filter_args(ps)
    _add_search_extras(ps)
    _content_selection_args(ps)
    ps.add_argument("--contents", action="store_true",
                    help="Enable content retrieval (text/highlights/summary/etc.) in this search.")
    _add_output_flags(ps)
    ps.set_defaults(func=cmd_search)

    # contents ---------------------------------------------------------------
    pc = sub.add_parser("contents", help="POST /contents — extract clean content from URLs.",
                        description="Extract clean text/highlights/summary from one or more known URLs.")
    pc.add_argument("urls", nargs="+", help="One or more URLs to extract content from.")
    _content_selection_args(pc)
    _add_output_flags(pc)
    pc.set_defaults(func=cmd_contents)

    # find-similar -----------------------------------------------------------
    pf = sub.add_parser("find-similar", help="POST /findSimilar — pages semantically similar to a URL.",
                        description="Find pages semantically similar to the given URL. Exa-specific; no Tavily equivalent.")
    pf.add_argument("url", help="The URL to find similar pages to.")
    pf.add_argument("-n", "--num-results", type=int, default=None, help="Number of results.")
    pf.add_argument("--category", default=None,
                    choices=["company", "people", "publication", "news", "personal site", "financial report", "research paper", "pdf"],
                    help="Restrict to a category index.")
    _common_search_filter_args(pf)
    _content_selection_args(pf)
    pf.add_argument("--contents", action="store_true", help="Enable content retrieval in this search.")
    _add_output_flags(pf)
    pf.set_defaults(func=cmd_find_similar)

    # answer -----------------------------------------------------------------
    pa = sub.add_parser("answer", help="POST /answer — a generated answer with citations.",
                        description="Ask a question; get a generated answer grounded in web sources, with citations.")
    pa.add_argument("query", help="The question to answer. Use '-' to read from stdin.")
    pa.add_argument("--text", action="store_true", help="Include full source text in citations.")
    pa.add_argument("--output-schema", default=None, metavar="FILE|JSON",
                    help="JSON schema file (@path) or inline JSON for structured answer output.")
    pa.add_argument("--stream", action="store_true", help="Stream the answer token-by-token (SSE). Ignored with --json.")
    _add_output_flags(pa)
    pa.set_defaults(func=cmd_answer)

    return parser


def _resolve_stdin_query(value: str | None) -> str:
    if value == "-":
        return sys.stdin.read().strip()
    return value or ""


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "query") and args.command in ("search", "answer"):
        args.query = _resolve_stdin_query(args.query)
        if not args.query:
            parser.error(f"{args.command}: a non-empty query is required (or pipe via '-')")
    try:
        return args.func(args)
    except client.ExaError as e:
        sys.stderr.write(f"exa: {e}\n")
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\ninterrupted\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
