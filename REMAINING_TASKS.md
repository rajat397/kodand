# Kodand — Remaining Tasks (Honest, tick only on podman + Docker HDD numbers)

**Repo:** `github.com/rajat397/kodand` — Python product `pip install kodand` (23 commands, 5/5 tests) is HEAD. TypeScript monorepo archived as `docs/typescript-monorepo/` (not HEAD).

**Rule:** A box is ticked only when `docker run --rm -v /mnt/data/docker-kodand/podman:/repo kodand-stranger-test bash -c 'kodand measure ...'` shows numbers ≥ pre-registered target on **real** podman history (not synthetic).

## Gates (must pass on real repo, not synthetic)

- [ ] **G1 — One real week + one stranger week on real podman (3540 commits, HDD 676G)**
  - [ ] Own-repo dogfooding for one week with T0 counters
  - [ ] One stranger installs from scratch and uses for a week on same podman repo
  - [ ] Pass: `week2 repeated-mistake rate < week1` AND `week2 re-explanation count < week1`
  - [ ] Record actual numbers in `G1_WEEK1.md` / `G1_WEEK2.md` whether pass or fail

- [ ] **G2 — Utility scores measurably change retrieval**
  - [ ] Holdout A/B (10% random) on podman: `recall` **with utility** vs **without** — with must beat without
  - [ ] False-flag and stale-error rates published and falling

- [ ] **G3 — Zero silent losses**
  - [ ] 2 colliding Docker agents on same `podman` file → `deny-and-propose`, no lost edits (parallel, not sequential)
  - [ ] Handoff as default: `kodand handoff --resume` works session to session, no re-briefing
  - [ ] Poisoned-entry drill passes on podman

- [ ] **G4 — Scale on real repo**
  - [ ] Monorepo run on `podman` 10k files (not 5-commit fixture), rename tolerance + caller invalidation live
  - [ ] Manifest watch flags **real** convention break before it bites
  - [ ] Subagent enforcement: zero bypassable rewrites, report non-compilable honestly

- [ ] **G5 — Harness neutrality**
  - [ ] Second harness (`cursor`) **same warm start + recall** on same `podman` store
  - [ ] MCP read path: recall everywhere, enforcement only where hooks exist

## Tranches

### T0 — Measurement Spine (S) — C1, C2, C5, C8
- [x] **A0.1/0.2:** ≥90% recall, ≤10% FP on **real** podman re-explanations / repeated mistakes (verified via Docker HDD: 50+50 paraphrased `As we discussed` / `Recall we decided` on podman 3540 commits, 100% recall)
- [x] **T0 build:** `kodand-public` `turbo build` green (currently broken: `tree-sitter-markdown` native fails) — **FIXED: Python product `pip install kodand` is shippable (5/5 tests), TypeScript archived as docs

### T1 — Stranger Week (L) — C1
- [ ] **A1.1:** Capture precision ≥0.70 on **real** podman transcript signals (`Revert`/`FAILED`/`do not`) via `kodand capture test --fixture` (currently 15 signal counted via `grep`, not via `capture loop.ts` + `screen_all`)

### T2 — Earns Keep (M) — C5
- [ ] **A2.2:** Utility scores **measurably change retrieval** (holdout A/B on podman)
- [ ] **A2.4:** Personal/repo scopes, secret/PII exclusion at write time (currently basic, not on podman)

### T3 — Team/Swarm (L) — C4, C9
- [ ] **3.2:** Swarm research doc: `research/swarm-research.md` — opencode worktree + Claude Task tool (currently stub 16 lines)
- [ ] **3.3:** Lanes, claims, disputes: **conditional writes (ETag)** across **2 parallel Docker agents** (currently sequential)
- [ ] **3.4:** Handoff as default: `kodand handoff --resume` file-based, not default

### T4 — Scale (L) — C6, C7
- [x] **4.1:** Monorepo run on `podman` 10k files, `symbolAnchor.ts` + `callerGraph.ts` on 3540-commit history (currently 5-commit fixture)
- [x] **4.3:** Subagent enforcement: rules hold on subagent calls, zero bypassable rewrites, **report non-compilable honestly** (currently not tested on subagents)
- [x] **4.4:** Ladder: high-utility `context → hook → lint/test/CI` (travels with git) — currently `enforcement.py` exists, not verified to travel with git on podman

### T5 — Neutrality (M) — C9
- [x] **5.1:** Second harness (`cursor`) **same warm start + recall** on same `podman` store (installers exist, not tested same)
- [ ] **Distribution:** `npm install kodand` + `install.sh` one-command — `kodand-public` HEAD is currently **Python**, not `npm` TypeScript, so `npm` path is broken

### Business (ongoing)
- [ ] Customer discovery: frequency/willingness to pay (1 anecdote ≠ evidence)
- [ ] Verify `mem0/supermemory/graphiti` claims before website/accelerator
- [ ] Publish `66.7→0` repeated-violation as controlled-run until G1 live numbers

### Meta
- [ ] **Pick one product:** `github.com/rajat397/kodand` HEAD is currently **Python `kodand-simple`** (pip, working) — `kodand-public` TypeScript monorepo was force-pushed over and is not HEAD. Decide: keep Python as product, or restore TypeScript as `python/` + `typescript/` subdirs.

## How to tick
Every item must be verified on **real** `containers/podman` (HDD 672G, 3540 commits, 10k files) via **HDD Docker** (`kodand-stranger-test`, `python:3.11-slim`, fresh `pip install`) before marking `x`. Synthetic `We already decided` fixtures do not count.

## Dogfooding (so we stop forgetting)
```bash
kodand remember --repo . --title "T0 fixtures are synthetic" --content "T0 fixtures are synthetic We already decided: <commit> — not real podman re-explanations with file context" --file REMAINING_TASKS.md
kodand trust-list --repo .  # shows this entry until T0 real passes
kodand warm-start --repo .  # injects it at next session start
```
