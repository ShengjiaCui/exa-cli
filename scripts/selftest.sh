#!/usr/bin/env bash
# exa-cli selftest — 14-point health check (mirrors tavily-rotator/scripts/selftest.sh format).
# Hits the real Exa API (basic search/contents calls are free-tier-cheap).
# Usage: bash scripts/selftest.sh   (EXA_API_KEY must be resolvable)
# Exit: 0 if all pass, 1 if any fail.
set -u

PASS=0; FAIL=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Resolve EXA_API_KEY: env > launchctl > zshrc grep (in priority order).
if [ -z "${EXA_API_KEY:-}" ]; then
  EXA_API_KEY="$(launchctl getenv EXA_API_KEY 2>/dev/null || true)"
fi
if [ -z "${EXA_API_KEY:-}" ]; then
  EXA_API_KEY="$(grep -E '^export EXA_API_KEY=' "$HOME/.zshrc" 2>/dev/null | sed -E 's/.*="(.*)"/\1/' || true)"
fi
export EXA_API_KEY

ok()   { echo "✓ $1"; PASS=$((PASS+1)); }
fail() { echo "✗ $1"; FAIL=$((FAIL+1)); }
check(){ if eval "$2" >/dev/null 2>&1; then ok "$1"; else fail "$1"; fi; }

echo "exa-cli selftest — 14 checks"
echo "----------------------------------------"

# 1. Binary on PATH
check "1. exa binary on PATH" 'command -v exa'

# 2. Version output
check "2. exa --version works" 'exa --version 2>&1 | grep -q "exa-cli"'

# 3. EXA_API_KEY resolvable
check "3. EXA_API_KEY is set (len > 10)" '[ "${#EXA_API_KEY}" -gt 10 ]'

# 4. --help lists all 4 subcommands
check "4. --help shows search/contents/find-similar/answer" \
  'exa --help 2>&1 | grep -q "search" && exa --help 2>&1 | grep -q "contents" && exa --help 2>&1 | grep -q "find-similar" && exa --help 2>&1 | grep -q "answer"'

# 5. search basic e2e
check "5. search returns results" 'exa search "test query" --num-results 1 --json | jq -e ".results | length >= 1"'

# 6. search --json has requestId
check "6. search --json has requestId" 'exa search "test" --num-results 1 --json | jq -e ".requestId"'

# 7. contents e2e
check "7. contents extracts text" 'exa contents https://exa.ai --text | grep -qi "exa"'

# 8. find-similar e2e
check "8. find-similar returns pages with score" 'exa find-similar https://exa.ai --num-results 2 --json | jq -e ".results[0].score != null"'

# 9. answer e2e
check "9. answer returns answer + citations" 'exa answer "what is 2+2" --json | jq -e ".answer and (.citations | length >= 1)"'

# 10. outputSchema produces structured output
check "10. outputSchema yields output field" \
  'exa search "top companies" --type deep --num-results 2 --output-schema "{\"type\":\"object\",\"properties\":{\"x\":{\"type\":\"string\"}}}" --json | jq -e ".output"'

# 11. text.maxCharacters truncates precisely
check "11. text.maxCharacters truncates" '[ $(exa search "react" --num-results 1 --contents --text --text-max-chars 150 --json | jq ".results[0].text | length") -le 200 ]'

# 12. skill symlinks resolve
check "12. all 5 exa skills resolve" \
  'for s in exa-cli exa-search exa-contents exa-find-similar exa-answer; do [ -f "$HOME/.zcode/skills/$s/SKILL.md" ] || exit 1; done'

# 13. Error: missing key → exit 1
check "13. missing EXA_API_KEY exits 1 with error" 'EXA_API_KEY="" exa search "x" 2>/dev/null; [ $? -ne 0 ]'

# 14. Error: no subcommand → exit non-zero with usage
check "14. no subcommand exits non-zero" 'exa 2>/dev/null; [ $? -ne 0 ]'

echo "----------------------------------------"
echo "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
