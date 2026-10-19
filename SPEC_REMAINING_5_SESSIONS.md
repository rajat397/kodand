# Kodand — Remaining 5 Sessions Detailed Spec (G1-G5 Gates on Real Red Hat Podman + HDD Docker)

**Repo:** containers/podman (Red Hat, 3540 commits, 10k files, Go) — `/mnt/data/docker-kodand/podman`
**HDD:** 672G avail | **Docker:** `kodand-simple` (pip, 23 commands, 5/5 tests) → `kodand-g1-stranger` image
**Principle:** Every session names C-line, pre-registers acceptance numbers, judges against them, not effort. Gates are real use (dogfooding + stranger), not controlled runs.

---

## Session 1: T0 Measurement Spine — Make North-Star Computable on Podman

**C-lines:** C1, C2, C5, C8 | **Size S**

**Why:** Without counters, G1-G5 cannot be judged. This session makes `repeated-mistake rate` and `re-explanation count` computable from logs alone for any ISO week.

**Pre-registered acceptance:**

| ID | Criterion | Target | How measured on podman |
|----|-----------|--------|------------------------|
| A0.1 | Re-explanation counter detects re-stating known decision | ≥90% recall, ≤10% FP | `fixtures/reexplain.jsonl` 50 re-explanations (We already decided: <commit msg> from podman log) + 50 novel (New feature idea) → `kodand measure reexplain --fixture` |
| A0.2 | Repeated-mistake counter detects repeating corrected mistake | ≥90% recall, ≤10% FP | `fixtures/mistake.jsonl` 50 repeated (same tool/file/error) + 50 novel → `kodand measure mistake --fixture` |
| A0.3 | Event log captures every capture/injected/outcome with provenance | 100% | `kodand measure events --verify` (every event has ts/kind/entry_id/provenance) on podman |
| A0.4 | Cost log per mechanism per session | 100% | `kodand measure cost --verify` |
| A0.5 | North-star numbers from logs alone | `kodand week --repo /repo` outputs both numbers for any week | `kodand week --repo /mnt/data/docker-kodand/podman --verify` |

**Design on podman:**
- `reexplanation.ts`: Jaccard on tokenized content (stopwords removed, len>2, threshold 0.75) + marker heuristic (`we already...`, `as I said`, `remember we...`) + overlap >0.4 → re-explanation. Logged `kind=reexplanation`.
- `repeatedMistake.ts`: signature = hash(tool|file|symbol|errorType), search `correction` memories last 30d, Jaccard >0.7 → repeated. Logged `kind=repeated_mistake`.
- `eventsLog.ts`: `EventLogger` buffer 10, flush 5s, `ts/kind/entry_id/provenance/detail` → `.kodand/events.log` + SQLite `events`
- `costLog.ts`: `CostLogger` per mechanism, `tokensIn/Out/Reasoning/latencyMs/model/success` → `cost.log`
- `weekReport.ts`: ISO YYYY-Www, `repeated-mistake rate = repeated/outcome else n/a`, `re-explanation count` from logs alone.

**Docker HDD verification:**
```bash
docker run --rm -v /mnt/data/docker-kodand/podman:/repo -v /tmp/kodand-simple:/kodand kodand-stranger-test bash -c '
cd /repo && pip install -q /kodand && kodand measure reexplain --fixture /kodand/packages/core/src/measure/fixtures/reexplain.jsonl # expect ≥90%
kodand measure mistake --fixture /kodand/packages/core/src/measure/fixtures/mistake.jsonl
kodand measure events --verify && kodand measure cost --verify
kodand week --repo /repo --verify
' 
```

**Kill:** precision <90% after 2 passes → add file context + surrounding turns, not thresholds.

**Files:** `packages/core/src/measure/{reexplanation.ts,repeatedMistake.ts,eventsLog.ts,costLog.ts,weekReport.ts,index.ts,fixtures/}` + `packages/storage/src/sqlite` tables + `packages/cli/src/measure.ts`

---

## Session 2: T1 Stranger Week — Close the Loop on Podman

**C-lines:** C1 | **Size L**

**Why:** The loop is open at first link. With no live entries, C5/C6/C8 cannot be validated.

**Pre-registered acceptance:**

| ID | Target | How measured on podman |
|----|--------|------------------------|
| A1.1 | Capture precision ≥0.70 on podman signals | `fixtures/capture.jsonl` 15 signal (do not/never/Revert/FAILED from podman log) + 50 noise → `kodand capture test --fixture` |
| A1.2 | Explicit `remember this` ≈0/week | `kodand capture explicit --fixture` |
| A1.3 | Review queue ≤5/day | `kodand capture status` |
| A1.4 | North-star computable | `kodand week --repo /repo` |

**Design on podman:**
- Signals: `T_CORRECTION` (no, fix/use/not), `T_REVERT` (Revert), `T_TESTFAIL` (FAILED/FAIL:/AssertionError), `T_CONSTRAINT` (do not/never, low)
- Pipeline: `emitCandidates → _evidential → _newCandidate → screen_all(S1-W3) → route` (high→store, low→queue, DROP→drops with verbatim reason)
- Docker: `podman` 3540 commits, `git log --grep=Revert` → 12 signals in 500

**Kill:** precision <0.70 after 2 passes → rethink source, not thresholds.

---

## Session 3: T2 Memory Earns Its Keep — Utility Drives Behavior on Podman

**C-lines:** C5 | **Size M (needs G1 data, but design + scaffolding now)**

**Pre-registered acceptance:**

| ID | Target |
|----|--------|
| A2.1 | Each applied entry marked avoided/caused/noise via env + one-tap, 10% holdout for counterfactual |
| A2.2 | Retrieval rank/promotion/decay follow score; low retired, surfaced |
| A2.3 | Lazy validation at apply time, warn-only never blocking |
| A2.4 | Scopes personal/repo, secret/PII exclusion at write time |

**Design on podman:**
- `outcomeLabeler.ts` + `utilityScorer.ts` (score = avoided*1 - caused*1 + noise*0.1)
- `lazyValidation.ts` at apply time, `scopeManager.ts` repo/personal
- Docker: `kodand outcome-label --holdout` + `kodand utility` + `kodand trust --decay` on podman

---

## Session 4: T3 Team/Swarm + T4 Scale — On Podman Monorepo

**C-lines:** C4, C6, C7 | **Size L**

**Pre-registered acceptance:**

| ID | Target |
|----|--------|
| A3.1 | Team promotion: provenance + 2 reviewers, poison drill PASS |
| A3.2 | Swarm research doc: worktrees, context sharing, merge points, hook coverage |
| A3.3 | Lanes, claims, disputes: ETag, claim/release, deny-and-propose |
| A3.4 | Handoff as default: decided/done/blocked → s2 resumes |
| A4.1 | Monorepo run: podman 10k files, rename tolerance + caller invalidation live |
| A4.2 | Manifest watch: flag convention on deps diff, catch real break |
| A4.3 | Subagent enforcement: zero bypassable rewrites, report non-compilable |
| A4.4 | Ladder: context→hook→lint/test/CI (travels with git) |
| A4.5 | Weekly surface: blocked/held/validated weekly |

**Design on podman:**
- Team: `teamScope.ts` + poison drill, Swarm: `lanes.ts` (claim file + lanes.json), Handoff: `intentLedger.ts`, Anchor: `symbolAnchor.ts` + `callerGraph.ts`

**Kill:** 0 silent losses must hold.

---

## Session 5: T5 Harness Neutrality — Second Harness on Podman

**C-lines:** C9 | **Size M**

**Pre-registered acceptance:**

| ID | Target |
|----|--------|
| A5.1 | Same store, second harness (cursor), same warm start + recall |
| A5.2 | MCP read path: recall everywhere, enforcement only where hooks exist |
| A5.3 | Cross-repo scope: org/team/repo/session inheritance, privacy |

**Design on podman:**
- `cursor/adapter.ts` same store, `mcp/readPath.ts` recall everywhere, `crossRepo.ts` inheritance
- Docker: `kodand install cursor` + `opencode` on same podman store, switch harness mid-project, re-explains nothing

**Gate G5:** switch harnesses, re-explains nothing.

---

## G1 Gate (Week 1 + Stranger, real use, not controlled)

- Own-repo dogfooding on podman for one week with T0 counters
- One stranger installs from scratch on podman and uses for a week
- Pass: `week2 repeated-mistake rate < week1`, `week2 re-explanation count < week1`, all 1.x hold, stranger keeps it installed
- Record numbers in changelog either way

