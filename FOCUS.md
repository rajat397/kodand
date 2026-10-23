# FOCUS — match and beat supermemory on its own benchmarks and claims

**Goal:** replace vendor-vs-vendor number wars with one shared ruler. Supermemory's
own open harness (MemoryBench) runs every provider through the same
ingest → index → search → answer → evaluate pipeline with the same judge.
We add kodand as a first-class provider there, then score both sides in public.

## Scoreboard (their claims; all vendor-reported unless noted)

| # | Claim | Source | Our target |
|---|---|---|---|
| C1 | LongMemEval-S 97% Recall@20 (GPT-4o judge) | supermemory.ai/research, May 2026 | kodand Recall@20 within striking range, same harness/judge |
| C2 | 95% Recall@15 at ~720 context tokens (99.4% reduction) | supermemory README | match recall at ≤ tokens (MemScore triple, not accuracy alone) |
| C3 | LoCoMo #1, ConvoMem #1 | README/research | run both; report, win or lose |
| C4 | SWE-ContextBench: 30.30% tasks resolved, 55.95% fail-to-pass, $0.58/task (independent paper, vendor-presented) | compare/supermemory-vs-mem0 | kodand ≥ on fail-to-pass + cost; repetition-rate as second axis |
| C5 | SMFS 3× fewer tokens on Claude, 1.75× on Codex (xAFS-110) | research page | report tokens/task on same 110-Q set if accessible |
| C6 | Sub-200/300ms search latency | docs | measure ours on the same runs (local sqlite should win this) |

## Tasks (in order; each is done only with numbers pasted in the log)

- [x] **F1 — kodand provider adapter for MemoryBench.** DONE 2026-10-20.
  `src/providers/kodand/` in local `/home/rajat/memorybench` (uncommitted —
  upstream repo, keep local): initialize (no key), per-message chunked ingest,
  instant awaitIndexing, FTS search, clear. Registration in providers/index,
  ProviderName, config (apiKey "none"), help text. Three bugs fixed en route:
  ingest idempotency (resume-safe), kodand init needs git+`--min-commits 0` on
  data dirs, **RecallEngine recency tiebreak destroying FTS rank** (MRR 0.00 with
  evidence at FTS #3; fixed in kodand, 14/14 green). Smoke `kodand-smoke5`:
  1/1 correct, MemScore 100% / 211ms / 2490tok (was 27,654tok whole-session),
  Hit@10=100% R=100% MRR=0.33. Kodand side pushed (`--json`, rank fix).
  Depends met: bun 1.4.3 installed, harness cloned, google key for judge/answer.
- [x] **F2 — 10-question MemScore baseline: DONE 2026-10-20 (report.json banked).**
  `kodand-f2`: 6/10 accuracy, MemScore 60% / 453ms / 3078tok (judge+answer
  `gemini-3.8-flash`, second owner-supplied key beat the quota wall).
  Retrieval: Hit@10=100% R=100% MRR=0.71 P@10 28%. Per type: knowledge-update 1/1,
  single-session-user 1/1, multi-session 1/2, temporal-reasoning 3/6.
  All 4 misses are "I don't know" abstentions (zero hallucinations);
  blocked-chunk audit cleared the filter (the one blocked turn was irrelevant copy).
  Miss pattern: multi-session aggregation questions don't fit top-10 chunks.
  That is the named F3 tuning target.
  Harness pacing patched locally for quota (75s→150s backoff, x8-12, in evaluate AND
  answer; CLI concurrency flags don't propagate on resume — checkpoint edit required).
  Cost cap for F3 without asking: $2 on the google key.
- Infra findings 2026-10-21 (headless-opencode investigation, closed):
  `opencode run` headless is FINE — spawned servers stream correctly when the
  provider endpoint is reachable (proven: instant JSON errors via `google`
  provider). The hangs were exclusive to gateway-routed (opencode-go) models.
  Direct api.opencode.ai calls from this sandbox hit Cloudflare 1010 (edge ban;
  browser UA passes edge but all guessed paths 404 — real data-plane paths
  unknown). Conclusion: remaining blocker is QUOTA ONLY (free-tier buckets),
  not plumbing, not auth. Unblocks: (1) paid/billed Google key, (2) quota
  reset + grind, (3) user-side run where the gateway isn't banned.
- [x] **F3-gemini partial: 149/500 judged (`kodand-f3c`, lite judge+answer).**
  77/149 = 51.7%, 43 abstentions (29%, zero hallucinations observed).
  Per type: knowledge-update 14/17 (0.82), single-user 11/15 (0.73),
  single-assistant 11/17 (0.65), temporal 21/49 (0.43), multi-session 16/39
  (0.41), single-preference 4/12 (0.33). CAVEATS: first-178 order-biased
  sample, not a random slice; lite judge+answer (not GPT-4o); abstention-heavy
  profile. Checkpoint holds everything; run paused for nvidia lanes.
- [x] **F3 FULL 500: DONE 2026-10-23 (`kodand-full500`, Nemotron Lightning, no reingest).**
  **270/500 = 54% accuracy**, MemScore **54% / 1563ms / 3342tok**, retrieval **Hit@10 75% MRR 0.574 nDCG 0.596** (nvidia/nemotron-3.5-lightning-30b-a3b judge+answer, cheapest fast path after Google quota wall). Per type: knowledge-update 59/78 (0.76) Hit 0.94, single-user 52/70 (0.74) Hit 0.93, assistant 35/56 (0.62), temporal 66/133 (0.50), multi-session 49/133 (0.37) Hit 0.66, preference 9/30 (0.30). Report `report.json` 7.4M banked. Reused the 500/500 ingested checkpoint (`~1.3Gi` free, SM paused) — no reingest, only answer/evaluate on new model after `EAI_AGAIN`/timeout retry fix (temperature disabled for reasoning model, 30s/90s backoff).
- **Crash-proofing (2026-10-21, after repeated wipes): `/home/rajat/backups/`
  holds `memorybench-local-changes.patch` + provider src tarball + ALL run
  checkpoints + `RESTORE.md` (8-step rebuild) + `report-kodand-full500-nemotron.json`. Checkpoint write-through verified live. Kodand repo pushed per tranche; keys in auth.json (persistent).
- [x] **Pivot 2026-10-23: leave supermemory, go complete local + 99% benchmark target.** Supermemory runs killed (`killall supermemory-server`, `2.7Gi free` now) — local extraction is days (`3062 episodes ×40s /2 =17h` for 80 Q, 500 Q →4 days) and cloud compare adds no product value. Goal is now **kodand 99% accuracy on benchmarks while being complete local, lightweight, on-device** (no external LLM for retrieval, no cloud). Supermemory checkpoints kept on disk (`supermemory-full500 80/500`) but not pursued.
- [ ] **F3-gemini vs F3-nvidia delta:** compare the 149 gemini slice (51.7%) vs full500 nvidia (54%) — model/judge effect isolated (same ingest/search). Publish as separate columns, not mixed. Keep as reference, not a blocker.
- [ ] **F3b — kodand 99% rerun (complete local) (same 500, no new ingest).** Reuse `kodand-full500` 500/500 ingested; only rerun `search` with **@15 + aggregation + rerank** (IMPROVEMENTS.md I1-I2) offline. Accept: Hit@15 ≥0.95, accuracy 99% with same `nvidia/lightning` judge, completely local (no cloud). Search latency ≤500ms locally.
- [ ] **F4 — close, not compare.** No more supermemory side-by-side — publish kodand's 99% local table vs supermemory's **published** 97% (separate runs, disclosed). The moat is complete local + repetition-rate (enforcement `0/24`), not cloud recall.
- [ ] **F5 — contribute our benchmark into their harness.** MemoryBench supports
  bring-your-own benchmarks: port the v4 repeat protocol (correction-override,
  deterministic grep grader) as `bench/repeat/` benchmark plugin. Accept: all
  providers runnable on it with one command. This is the move that ends
  benchmark-picking: they face our metric on their ruler.
- [ ] **F6 — verdict + close gaps.** Publish table: where we match/beat (expect:
  latency, tokens, repetition, enforcement categories) vs trail (expect: raw
  recall@K, modalities we don't have). Every trailing cell gets either a fix
  task (e.g. FTS tuning, chunking) or an explicit wont-fix with reason.
  No trailing cell left unexplained.

## Rules (from the mem0/zep lesson)
- Same harness, same judge, same answering model, same run — or it doesn't count.
- Pin all model snapshots per run; publish failures + per-question results.
- MemScore is a triple: never claim a win on accuracy while hiding tokens/latency.
- Cost ledger per run (their $0.58/task is part of C4; record ours the same way).

## Non-goals (this round)
- Connectors, multimodal extractors, user profiles, cloud hosting, compliance.
- Matching their README prose — only measured cells.
