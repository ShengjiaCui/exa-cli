<div align="center">

# exa-cli

A friendly command-line tool for the [Exa.ai](https://exa.ai) search API.

Search the web · Extract page content · Find similar pages · Get cited answers

**[English](README.md)** | [中文](README.zh-CN.md)

</div>

---

## What is this?

[Exa.ai](https://exa.ai) is a search engine built for AI — it returns clean,
structured results instead of ad-filled HTML. But Exa only provides Python/JS
SDKs, **no command-line tool**. This project fills that gap.

After installing, you get an `exa` command that works right in your terminal:

```bash
$ exa search "who invented the transformer architecture"

2 result(s) for: who invented the transformer architecture

1. Attention Is All You Need
   https://arxiv.org/abs/1706.03762
   score: 0.95

2. The Illustrated Transformer
   https://jalammar.github.io/illustrated-transformer/
   score: 0.91
```

## Quick start (2 minutes)

### Step 1 — Install

```bash
# Requires Python 3.9+ and uv (https://docs.astral.sh/uv/)
uv tool install git+https://github.com/ShengjiaCui/exa-cli.git
```

Verify it's installed:

```bash
exa --version
# exa-cli 0.1.0
```

### Step 2 — Get an API key

1. Go to [exa.ai/dashboard](https://exa.ai/dashboard)
2. Create a free account (you get **$20 in free credits** + **$10/month**)
3. Copy your API key

### Step 3 — Set your key

Add this to your shell profile (`~/.bashrc`, `~/.zshrc`, or PowerShell profile):

```bash
export EXA_API_KEY=your-key-here
```

Then reload your shell (or open a new terminal).

### Step 4 — Search!

```bash
exa search "latest news about AI" --num-results 5
```

That's it. You're done. 🎉

---

## Commands

### `exa search` — Search the web

The most common command. Finds web pages matching your query.

```bash
# Basic search
exa search "react hooks tutorial"

# More results
exa search "machine learning" --num-results 10

# Search + get page content in one call (saves a round-trip)
exa search "quantum computing" --contents --highlights

# Only search specific sites
exa search "SEC filings" --include-domains sec.gov

# Recent results only
exa search "AI news" --start-date 2026-07-01

# Academic papers
exa search "scaling laws" --category "research paper"
```

**Search depth** — control speed vs quality with `--type`:

| `--type` | Speed | Use case |
|----------|-------|----------|
| `instant` | ~250ms | Real-time autocomplete |
| `fast` | ~450ms | Quick lookups |
| `auto` *(default)* | ~1s | General purpose |
| `deep` | seconds | Complex multi-step queries |
| `deep-reasoning` | 12-40s | Hard research tasks |

### `exa contents` — Extract content from a URL

Already have a URL? Get its clean text without boilerplate (nav bars, ads, etc).

```bash
# Full text
exa contents https://example.com --text

# Just the key highlights (token-efficient)
exa contents https://example.com --highlights

# AI-generated summary
exa contents https://example.com --summary

# Multiple URLs at once
exa contents https://a.com https://b.com https://c.com --text
```

### `exa find-similar` — Find pages similar to a URL *(Exa-unique)*

Give it one good page, get back pages that are semantically related.
**No other search engine offers this as a first-class operation.**

```bash
exa find-similar https://arxiv.org/abs/1706.03762 --num-results 5

# Exclude the source domain (avoid near-duplicates)
exa find-similar https://some-blog.com/post --exclude-domains some-blog.com
```

### `exa answer` — Ask a question, get a cited answer

```bash
exa answer "who founded exa.ai?"

# Answer:
# Exa.ai was founded by Will Bryk and Jeff Wang [1][2]...
#
# Sources:
# 1. Exa: The Search Engine for Developers — https://exa.ai/about
# 2. TechCrunch article — https://techcrunch.com/...

# Stream the answer live (tokens appear as they're generated)
exa answer "what is the latest in LLM scaling?" --stream
```

---

## Output options (all commands)

| Flag | What it does |
|------|-------------|
| `--json` | Structured JSON output (for scripts, piping, AI agents) |
| `-o FILE` | Save output to a file instead of printing |
| `-` (as query) | Read query from stdin: `echo "query" \| exa search -` |

```bash
# Pipe to jq to extract just the URLs
exa search "best python libraries" --json | jq -r '.results[].url'

# Save results to a file
exa search "AI news" -o results.json --json

# Read query from a pipe
cat my-questions.txt | exa answer - --json
```

---

## Advanced: structured output

Pass a JSON schema to extract specific fields across multiple pages:

```bash
exa search "top aerospace companies" --type deep --num-results 5 \
  --output-schema '{"type":"object","properties":{"companies":{"type":"array","items":{"type":"object","properties":{"name":{"type":"string"},"ceo":{"type":"string"}}}}}}' \
  --json
```

The response will contain an `output` field with structured data instead of free text.

---

## Advanced: content options

When using `--contents` with `exa search` or `exa find-similar`, you can
fine-tune what content comes back:

```bash
exa search "funding rounds" --contents \
  --text --text-max-chars 1000 \    # limit text length
  --highlights --highlights-query "amount raised" \  # focus highlights
  --summary --summary-query "extract valuation" \    # focus summary
  --subpages 3 --subpage-target docs \  # crawl subpages
  --json
```

Run `exa search --help` to see the complete list of options.

---

## How keys work (and optional rotation)

Exa's free tier gives **$10/month per account**. If you have multiple accounts,
you can use [exa-rotator](https://github.com/ShengjiaCui/exa-rotator) to
automatically rotate between keys before the monthly limit is hit.

This CLI reports each API call's cost (`costDollars` from the response) to the
rotator daemon if it's running. If the daemon isn't running, the CLI works
normally — this is completely optional.

---

## Testing

```bash
# Unit tests (fast, no API calls)
uv run pytest -v

# Integration test (hits real Exa API, ~10s)
bash scripts/selftest.sh
```

## Uninstall

```bash
uv tool uninstall exa-cli
# Remove the export line from your shell profile
```

---

## License

MIT
