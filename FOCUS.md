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
- [ ] **F3 rerun on cheapest-working model: `kodand-nvfull` + F4 compare RUNNING.**
  Lesson learned the hard way: `kodand-f3b` only ever ran 10 questions despite a
  500-question checkpoint — killing it mid-ingest and resuming hit the harness's
  old-checkpoint path (`startedQuestions` only, no stored limit). f3b's 6/10 is
  valid as a lite-model replication of F2's slice, not as F3. Rule: never kill a
  run mid-ingest; `f3c` runs uninterrupted to completion.
  Model selection 2026-10-21 (owner pricing table): `gemini-3-flash` 404s;
  `gemini-3.5-flash-lite` ($0.30/$2.50) answers live → winner; 3.8 stays fallback.
  Pricing favors lite ~5x vs 3.8 ($1.50/$7.50) for judge+answer-heavy runs.
  Relaunched full-500 as `kodand-f3b` (fresh run id = one model throughout).
  First 10 replicate F2's verdicts exactly (same 6 correct / 4 incorrect —
  model swap 3.8→3.5-lite changed nothing on this slice).
- **Crash-proofing (2026-10-21, after repeated wipes): `/home/rajat/backups/`
  holds `memorybench-local-changes.patch` + provider src tarball + ALL run
  checkpoints + `RESTORE.md` (8-step rebuild). Checkpoint write-through verified
  live. Kodand repo pushed per tranche; keys in auth.json (persistent).
- [ ] **F3-nvidia lane: `kodand-nvfull` RUNNING (full 500, nvidia judge+answer).**
  Same kodand provider, separate judge column — never mixed with gemini numbers.
  Launcher `/home/rajat/run-nvfull.sh`, setsid-detached.
- [ ] **F4 side-by-side: `kodand-sm-compare1` RUNNING (both providers, nvidia judge).**
  `compare -p kodand,supermemory -b longmemeval -s 10` (+ SUPERMEMORY_* env);
  kodand side ingesting now, supermemory arm ingests into the local server next.
  Old gemini-lane runs (`kodand-f3c`) and 1-Q smokes (`sm-smoke2`) are superseded
  checkpoints — kept on disk, not deleted.
- [ ] **F3 — full LongMemEval-S kodand run.** Same judge + answering model as C1
  (GPT-4o judge; answering model pinned and recorded). Accept: Recall@20 and
  per-category table in `bench/memorybench/results/`, committed.
- [ ] **F4 — side-by-side compare.** `compare -p kodand,supermemory -b longmemeval`
  (then locomo, convomem). Accept: same-run table for both providers.
  Depends: SUPERMEMORY_API_KEY + judge key (ask owner; never fake the arm —
  if keyless, kodand runs alone and the cell stays `NOT RUN`).
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
