# exa-cli

**[English](README.md)** | [中文](README.zh-CN.md)

A thin command-line interface for the [Exa.ai](https://exa.ai) search API.

## Why

Exa has no official CLI (only Python/JS SDKs). This fills that gap so the
search engine can be used from the terminal and from AI agent skills.
Conventions: `EXA_API_KEY` from env, `--json` for structured output,
`-o FILE` to save, stdin via `-`. Zero runtime dependencies (stdlib only).

## Install

```bash
uv tool install ~/Projects/exa-cli
```

Then ensure `EXA_API_KEY` is in your environment:

```bash
# one-time, persisted across shells:
launchctl setenv EXA_API_KEY <your-key>
```

Verify:

```bash
exa --version
exa search "test" --json | jq '.results | length'
```

## Commands

All four Exa endpoints, mapped to subcommands:

| Command | Endpoint | Purpose |
|---------|----------|---------|
| `exa search` | `POST /search` | Semantic / keyword web search |
| `exa contents` | `POST /contents` | Extract clean content from URLs |
| `exa find-similar` | `POST /findSimilar` | Pages similar to a given URL (Exa-specific) |
| `exa answer` | `POST /answer` | Generated answer with citations |

**Full parameter coverage**: every parameter in Exa's [API reference](https://exa.ai/docs/reference/search-api-guide-for-coding-agents) is exposed — including nested `contents` objects (`text.maxCharacters`, `highlights.query`, `summary.schema`), `subpages`/`subpageTarget`, `maxAgeHours`/`livecrawlTimeout`, `outputSchema` (structured output), `systemPrompt`, `moderation`, `stream`, and more. Run `exa search --help` / `exa contents --help` / `exa find-similar --help` / `exa answer --help` for the complete flag list.

## Examples

```bash
# Basic search
exa search "latest developments in LLMs"

# Search with content in one call
exa search "react hooks tutorial" --contents --highlights --num-results 3

# Domain-filtered, recent
exa search "SEC filings" --include-domains sec.gov --start-date 2026-01-01

# JSON for agents / piping
exa search "quantum computing" --json | jq '.results[].url'

# Extract content from known URLs
exa contents https://example.com https://exa.ai --text

# Find pages similar to a URL (Exa-specific)
exa find-similar https://exa.ai --num-results 5

# Answer a question with citations
exa answer "what is exa.ai?"
exa answer "who founded exa?" --stream   # stream tokens live

# Read query from stdin
echo "what is rag" | exa answer - --json

# Save output
exa search "AI news" -o results.json --json
```

## Options (shared)

| Flag | Description |
|------|-------------|
| `--json` | Structured JSON output (for agents / piping). |
| `-o, --output FILE` | Write output to FILE instead of stdout. |
| `--timeout N` | HTTP timeout in seconds (default: 60). |

## Wire-format notes

- HTTP parameters use **camelCase** (`numResults`, `includeDomains`,
  `startPublishedDate`) per Exa's HTTP API. This CLI handles the translation.
- On `/search`, content params (`text`/`highlights`/`summary`) are nested
  inside a `contents` object — this CLI does that when you pass `--contents`.
- Deprecated upstream and intentionally not exposed: `useAutoprompt` (no-op),
  `includeUrls`/`excludeUrls` (use domains), `livecrawl:"always"` on search
  (use `contents.maxAgeHours`).

## Design

- **Zero runtime dependencies** — stdlib only (`urllib`, `json`, `argparse`).
  Keeps the `uv tool` install isolated; nothing to pin.
- **Auth via `EXA_API_KEY` only** — reads from the environment.
- **Thin, not smart** — passes responses through largely uninterpreted. If Exa
  changes its response shape, only the human-renderer needs updating.

## Cost reporting (exa-rotator integration)

Every Exa `/search` and `/answer` response includes a `costDollars.total` field.
This CLI reports it to the [exa-rotator](https://github.com/ShengjiaCui/exa-rotator)
daemon (if running) via a fire-and-forget POST to `127.0.0.1:8732/api/ingest-cost`.
This lets the rotator track per-key monthly spending and rotate between accounts
before the free-tier limit is hit — without needing Exa's admin API.

If the rotator daemon isn't running, the POST fails silently — the CLI works normally.

## Testing

Two test layers:

**Unit tests** (pytest, no API calls, ~0.1s) — mock `client.request` and assert the wire-format body is correct (camelCase translation, contents nesting, filter logic, error normalization):

```bash
uv run pytest -v          # 107 tests
uv run pytest -q          # quiet
```

**Self-test** (bash, hits real API, ~10s) — 14-point health check for ops verification:

```bash
bash scripts/selftest.sh  # 14 checks, exit 0 if all pass
```

Run both before committing:

```bash
uv run pytest -q && bash scripts/selftest.sh
```
