#!/bin/bash
set -e
# Enforceable rapid loop — fails CI if bypassed
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail() { echo "ENFORCE FAIL: $1" >&2; exit 1; }

[[ -f "$ROOT/bench/adversarial-30.json" ]] || fail "bench/adversarial-30.json missing"
[[ -x "$ROOT/bench/run-adv30.sh" ]] || fail "bench/run-adv30.sh not executable"
[[ -d "$ROOT/docs/kill-tests" ]] || fail "docs/kill-tests missing"

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
