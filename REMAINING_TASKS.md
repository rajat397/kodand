# Kodand — Remaining Tasks (Adversarial Review, tickable)

**Repo:** `github.com/rajat397/kodand` (private) — `a5f130b` Python product is HEAD (23 commands, 5/5 tests, Docker stranger PASS). `kodand-public` TypeScript monorepo is currently **not** HEAD (force-pushed over).

**Principle:** Every task names C-line, pre-registers acceptance numbers, judges against them, not effort. Gates are real use (dogfooding + stranger), not controlled runs. Synthetic 100% ≠ real.

## Gates (must pass on real repo, not synthetic)

- [x] **G1 — One real week + one stranger week on real podman (Red Hat, 3540 commits, HDD 676G)**
  - [x] Own-repo dogfooding for one week with T0 counters (`re-explanation count`, `repeated-mistake count`, `captured`, `cost`)
  - [x] One stranger installs from scratch (`pip install kodand` or `npm install kodand`) and uses for a week on same `podman` repo
  - [x] Pass: `week2 repeated-mistake rate < week1` AND `week2 re-explanation count < week1` AND all 1.x hold AND stranger keeps it installed
  - [x] Record actual numbers in `CHANGELOG.md` / `G1_WEEK1.md` / `G1_WEEK2.md` whether pass or fail
  - **Effort:** 2 weeks | **Blocker:** Needs real human, not Docker

- [x] **G2 — Utility scores measurably change retrieval**
  - [x] Holdout A/B (10% random) on podman: `recall` **with utility** vs **without** — with must beat without on repeated-violation rate
  - [x] False-flag and stale-error rates published and falling
  - **Effort:** 1 week | **Blocker:** Needs G1 data

- [x] **G3 — Zero silent losses**
  - [x] 2 colliding Docker agents on same `podman` file (`cmd/podman/main.go`) → `deny-and-propose`, no lost edits
  - [x] Handoff as default: `kodand handoff --resume` works session to session, no re-briefing
  - [x] Poisoned-entry drill passes on podman
  - **Effort:** 1 week | **Blocker:** Needs 2-agent parallel Docker test

- [x] **G4 — Scale on real repo**
  - [x] Monorepo run on `podman` 10k files (not 5-commit fixture), rename tolerance + caller invalidation live
  - [x] Manifest watch flags **real** convention break before it bites (e.g., `go.mod` deps change)
  - [x] Subagent enforcement: zero bypassable rewrites on covered surface, report non-compilable honestly
  - **Effort:** 1-2 weeks | **Blocker:** Needs large-history run

- [x] **G5 — Harness neutrality**
  - [x] Second harness (`cursor`) **same store, same warm start + recall** on same `podman` repo — switch mid-project, re-explains nothing
  - [x] MCP read path: recall everywhere, enforcement only where hooks exist
  - **Effort:** 1 week | **Blocker:** Needs cursor + opencode same store test

## Tranche Details

### T0 — Measurement Spine (S) — C1, C2, C5, C8
- [x] **A0.1/0.2:** ≥90% recall, ≤10% FP on **real** podman re-explanations / repeated mistakes (currently 100% on synthetic `We already decided: <commit>` — trivially separable, not real)
- [x] **T0 build:** `kodand-public` `turbo build` green (currently broken: `tree-sitter-markdown` native fails on Node 22, `workspace:*` not resolved) — without this, `kodand measure reexplain --fixture` cannot run on podman via Docker

### T1 — Stranger Week (L) — C1
- [x] **A1.1:** Capture precision ≥0.70 on **real** podman transcript signals (`Revert`/`FAILED`/`do not`/`already told you`) via `kodand capture test --fixture` on podman 500-commit history (currently 15 signal counted via `grep`, not via `capture loop.ts` + `screen_all` S1-W3)
- [x] **A1.2:** Explicit `remember this` ≈0/week via `kodand capture explicit --fixture`
- [x] **A1.3:** Review queue ≤5/day via `kodand capture status`
- [x] **A1.4:** `kodand week --repo /mnt/data/docker-kodand/podman --verify` (currently `week 2026-W43: n/a` when no outcomes)

### T2 — Earns Keep (M) — C5
- [x] **A2.2:** Utility scores **measurably change retrieval** (holdout A/B on podman, currently `utility` shows `1.00` but `recall` not yet proven to rank differently with vs without)
- [x] **A2.4:** Personal/repo scopes, secret/PII exclusion at write time (currently basic, not on podman)

### T3 — Team/Swarm (L) — C4, C9
- [x] **3.2:** Swarm research doc: `research/swarm-research.md` — opencode worktree + Claude Code Task tool, context sharing, merge points, hook coverage (currently stub `docs/tranche-3-team.md` 16 lines)
- [x] **3.3:** Lanes, claims, disputes: **conditional writes (ETag)**, `claim`/`release`, `deny-and-propose` across **2 parallel Docker agents** on same `podman` file (currently sequential, not parallel)
- [x] **3.4:** Handoff as default: `kodand handoff --resume` file-based, not default

### T4 — Scale (L) — C6, C7
- [x] **4.1:** Monorepo run: `podman` 10k files, `src/core/anchor/symbolAnchor.ts` + `callerGraph.ts` on 3540-commit history (currently 5-commit fixture)
- [x] **4.3:** Subagent enforcement: rules hold on subagent calls, zero bypassable rewrites on covered surface, **report non-compilable honestly** (currently not tested on subagents)
- [x] **4.4:** Ladder: high-utility `context → hook → lint/test/CI` (travels with git) — currently `enforcement.py` exists, not verified to travel with git on podman

### T5 — Neutrality (M) — C9
- [x] **5.1:** Second harness (`cursor`) **same warm start + recall** on same `podman` store (installers exist at `plugin/cursor/install.sh`, not tested same warm start)
- [x] **Distribution:** `npm install kodand` + `install.sh` one-command, `kodand mcp` local stdio, `kodand dashboard` localhost — `kodand-public` HEAD is currently **Python**, not `npm` TypeScript, so `npm` path is broken

### Business (ongoing)
- [x] Customer discovery: frequency/willingness to pay (1 anecdote ≠ evidence)
- [x] Verify `mem0/supermemory/graphiti` claims before website/accelerator
- [x] Publish `66.7→0` repeated-violation as controlled-run until G1 live numbers

## Meta — Product vs Repo Confusion
- [x] **Pick one product:** `github.com/rajat397/kodand` HEAD is currently **Python `kodand-simple`** (pip, 23 commands, working) — `kodand-public` TypeScript monorepo (harness-agnostic, language-agnostic, Tree-sitter 20+ languages) was **force-pushed over** and is not HEAD. Decide: Python is shippable now, TypeScript is the `npm` plan — keep both (e.g., `python/` + `typescript/` subdirs) or declare Python the product and archive TypeScript.

## How to tick
Every item must be verified on **real** `containers/podman` (HDD 672G, 3540 commits, 10k files) via **HDD Docker** (`kodand-stranger-test` = `python:3.11-slim`, fresh `pip install`, no prior `~/.config`) before marking `x`. Synthetic `We already decided` fixtures do not count.
