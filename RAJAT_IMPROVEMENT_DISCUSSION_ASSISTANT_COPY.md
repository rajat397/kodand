# Rajat's Improvement Discussion — Human Judgement (Frozen)

**Source:** adversarial review on `kodand-full500` 270/500 = 54% (Nemotron Lightning, 2026-10-23). This file is Rajat's human judgement, based purely on discussions between us. Do not edit without explicit instruction. The assistant keeps a separate evolving copy.

**Run:** `kodand-full500` 500/500 `270/500 = 54%` MemScore 54% / 1563ms / 3342tok retrieval Hit@10 75% MRR 0.574 nDCG 0.596 (nvidia/nemotron-3.5-lightning-30b-a3b judge+answer). Artifact: `~/memorybench/data/runs/kodand-full500/report.json` + `~/backups/report-kodand-full500-nemotron.json`.

## Top 5 limiting factors (why 54%, not 99%)

**1. Top-10 flat retrieval (caps → 75% Hit, not 95%) — P0, biggest**
* Evidence: Hit@10 0.75. multi-session 49/133 (0.37) Hit 0.66 vs single-user 52/70 (0.74) Hit 0.93. Multi-session evidence spread — 1 chunk insufficient.
* Limit: FTS LIMIT 10 (`memorybench/src/providers/kodand/index.ts:182`, `kodand/recall --limit 10`). Supermemory reports @15/@20 with aggregation.
* Fix: I1 @15 + aggregation (dedup+concat same haystack). Offline.

**2. No reranker (MRR 0.574 → rank ~2-3)**
* Evidence: MRR 0.574. Correct chunk mid-pack, 9 distractors before it.
* Limit: pure BM25 porter, no cross-encoder. Weights cached 105M in `~/.supermemory/models` not used.
* Fix: I2 local rerank top-15 → MRR 0.57→0.70 offline.

**3. Single-message chunking (temporal 0.50, multi-session 0.37)**
* Evidence: temporal-reasoning 66/133 (0.50) Hit 0.67, multi-session 0.37. chunkText() = 1 message = 1 chunk, no window.
* Limit: Date: stored but not indexed.
* Fix: I3 window ±1 + index Date: in FTS.

**4. Preference as recall, not profile (9/30 = 0.30 — worst)**
* Evidence: 0.30, Hit 0.63 mid but answer collapses.
* Limit: stateless recall, no user-profile cache.
* Fix: I5 one recall "preferences" ahead of every answer.

**5. Assistant vs user salience gap (0.62 Hit 0.73 vs 0.74 Hit 0.93)**
* Evidence: 11pp accuracy gap, 20pp Hit gap.
* Limit: FTS content only, assistant: not boosted.
* Fix: I4 boost assistant: via locator weight.

**Not the limit:** model (pinned nvidia), abstention profile (43/149, zero hallucinations) is strength.

---

## Assistant Evolution — 2026-10-23 pivot: make supermemory look like a dwarf

**New bar from Rajat:** not "match 97%" but **99% accuracy target, complete local, lightweight, on-device, fundamentally smarter** — kernel-reliable, compression-smart, IR-modern. Supermemory's hosted graph is a network call; we are a file.

**New research lens (examples, not verbatim):** Linux RCU/CoW/WAL → lock-free reads in `bridge.db` (already `WAL` + `seen` cache, now `ingest:8`); `zstd` + product quantization on `embgemma2`/`nomic-embed-text` (local) → `3342tok → ~1200tok` without MRR loss; image pyramids → 3-scale memory (message → session summary → haystack summary); IR beyond 1976 BM25 → learned sparse `SPLADEv3`/`uniCOIL`, late interaction `ColBERTv2` on-device, hybrid `WAND`; `OKF` (Google open knowledge format) as chunk schema vs `locator="session#i"` strings; LSM-tree for 500×50 write-heavy ingest; `HNSW` vs `IVF` for `<500ms` to beat their `sub-300ms` claim (local SQLite should win).

**Plan (research-first, code second, adversarial):**
1. Sweep authoritative only: `OKF` spec, `SPLADEv3`, `ColBERTv2`, `QMD` pipeline, Linux `RCU/WAL` — each gets one-page "useful for kodand? kill criteria" (needs 10 GPUs or 100M docs → out).
2. Bake-off offline: `embgemma2` + `bge-reranker` + `HNSW` vs `FTS15+aggregation` on same `kodand-full500` 500, same `nvidia/lightning` judge, fully offline. No supermemory re-run.
3. Your `RAJAT_IMPROVEMENT_DISCUSSION.md` stays frozen; this file is the evolving copy.

**Status 2026-10-23:** `F3 FULL 500 270/500=54%` banked (`975964c` human doc frozen), `supermemory-full500` killed (`2.7Gi free`), next is `I1 @15+aggregation` + `I2 rerank` offline on same 500 ingest (no reingest, no API).

---

## Lab — 2026-10-23: I9 Kodand as external memory (stateless amnesia) — evolving

**Problem:** `drift sweep → ingest 500` happened because top task in `FOCUS.md` wasn't recallable — `grep` vs `kodand recall` gate. Same `0/24` vs `0.875` mechanism as `wildcard` force-guard.

**Implementation (evolving):** `scripts/enforce-adversarial.sh` now `kodand remember --repo . --title "FOCUS top task" --content "$TOP_FOCUS"` then `kodand recall --query "top unchecked task in FOCUS"` and `BLOCKED` if top is `Literature sweep` but `ingest 500` attempted. Dogfooding: before any `bun run`, `kodand-full500`'s `FOCUS` is the memory, not `cat`.

**Next:** keep `bench/adversarial-30.json` as the 5-min oracle, `holdout30` never tuned on — this gate ensures we never drift to full `500` without passing `adv30` + `kill-test` verdict first.
