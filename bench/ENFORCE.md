# Enforceable Rapid Loop — Do Not Bypass

**Rule:** Any retrieval/ranking change that claims a win must:

1. Run `bench/run-adv30.sh` (30 adversarial fails, ~5 min, `nvidia/lightning` judge) — win is `+5` on `adversarial30`.
2. Validate **once** on `holdout30` (never tuned on) — if holdout doesn't move, kill the idea (overfit).
3. Update the relevant `docs/kill-tests/*.md` with "Verdict: PASS/ KILL + Hit/MRR delta" — no doc update = no merge.

**Enforcement:**
* `scripts/enforce-adversarial.sh` runs in CI and as a pre-commit hook. It fails if `bench/adversarial-30.json` is missing, `run-adv30.sh` not executable, or `docs/kill-tests/` has `NOT RUN` verdicts on a PR that touches `kodand/recall` / `memorybench/src/providers/kodand`.
* Checkpoint: `RAJAT_IMPROVEMENT_DISCUSSION.md` (your log) is auto-appended from discussions; `RAJAT_IMPROVEMENT_DISCUSSION_ASSISTANT_COPY.md` is the lab notebook. CI checks both exist.

**Override:** Only Rajat can bypass with `git commit --no-verify` + reason in commit message — logged, not silent.
