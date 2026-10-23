#!/bin/bash
set -e
# Enforceable rapid loop — fails CI if bypassed
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail() { echo "ENFORCE FAIL: $1" >&2; exit 1; }

[[ -f "$ROOT/bench/adversarial-30.json" ]] || fail "bench/adversarial-30.json missing"
[[ -x "$ROOT/bench/run-adv30.sh" ]] || fail "bench/run-adv30.sh not executable"
[[ -d "$ROOT/docs/kill-tests" ]] || fail "docs/kill-tests missing"

# I9: Kodand as external memory — top FOCUS task must be recallable, not just grepped
# Store FOCUS top task as recallable memory (best-effort, then recall as gate)
if command -v kodand >/dev/null 2>&1; then
  TOP_FOCUS=$(grep -m1 "^\- \[ \]" "$ROOT/FOCUS.md" 2>/dev/null | head -1 | cut -c1-120)
  if [[ -n "$TOP_FOCUS" ]]; then
    kodand remember --repo "$ROOT" --title "FOCUS top task" --content "$TOP_FOCUS" --file FOCUS.md --scope repo >/dev/null 2>&1 || true
    RECALL=$(kodand recall --repo "$ROOT" --query "top unchecked task in FOCUS" --limit 1 --json 2>/dev/null | grep -o '"content":"[^"]*"' | head -1 || true)
    if [[ -n "$RECALL" ]] && echo "$RECALL" | grep -q "Literature sweep\|kill-test"; then
      # If top task is sweep but ingest 500 is attempted, block (same gate as wildcard 0/24)
      if git diff --cached --name-only 2>/dev/null | grep -q "memorybench.*ingest"; then
        fail "FOCUS top task is sweep — run docs/kill-tests, not ingest 500 (kodand recall gate BLOCKED)"
      fi
    fi
  fi
fi

# If recall/provider touched, kill-tests must have verdicts
if git diff --name-only HEAD~1 2>/dev/null | grep -qE "kodand/recall|memorybench/src/providers/kodand"; then
  for f in "$ROOT/docs/kill-tests"/*.md; do
    grep -q "Verdict:" "$f" || fail "$f missing Verdict:"
    grep -q "NOT RUN" "$f" && fail "$f still NOT RUN — run adv30 first"
  done
fi

# Rajat's log must exist (auto-updated from discussions)
[[ -f "$ROOT/RAJAT_IMPROVEMENT_DISCUSSION.md" ]] || fail "RAJAT_IMPROVEMENT_DISCUSSION.md missing"
[[ -f "$ROOT/RAJAT_IMPROVEMENT_DISCUSSION_ASSISTANT_COPY.md" ]] || fail "assistant copy missing"

echo "ENFORCE OK: rapid loop + kill-tests present"
