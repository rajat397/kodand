# Rajat's Improvement Discussion — Human Judgement (Discussion Log)

**Source:** adversarial review on `kodand-full500` 270/500 = 54% (Nemotron Lightning, 2026-10-23). This file is Rajat's discussion log — updated automatically from our discussions. The assistant's custom research lives in `RAJAT_IMPROVEMENT_DISCUSSION_ASSISTANT_COPY.md` and will not overwrite this file's discussion entries.

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

## Discussion — 2026-10-23: Make supermemory look like a dwarf

**Rajat:** Purpose is to dwarf supermemory — think differently and better, via cutting-edge or classic but highly intelligent fundamentals (Linux kernel reliability like RCU/CoW/WAL, latest ML/AI, core CS, cross-domain like compression / image pyramids / IR, Google OKF, local `embgemma2`, OSS harness/RAG techniques). Learn from best engineering blogs but adapt to our scale — trust only authoritative sources after brutal adversarial usefulness analysis.

**Agreed lens:** Kernel RCU/WAL → lock-free `bridge.db`; `zstd` + PQ on `embgemma2`/`nomic-embed-text` → `3342tok→~1200tok`; pyramids → 3-scale memory (message→session→haystack); BM25 (1976) → learned sparse `SPLADEv3`/`ColBERTv2` hybrid on-device, `HNSW` vs `IVF`; `OKF` as typed chunk schema vs `locator="session#i"`; LSM-tree for write-heavy `500×50` ingest.

**New bar:** 99% offline, lightweight, on-device — no cloud, no API in retrieval. Supermemory local runs killed (`2.7Gi free`), pivot captured in `FOCUS.md:92f4c21`.

---

## Discussion — 2026-10-23: Kodand as external memory for its own builder (stateless amnesia)

**Rajat:** "No external memory between turns — I'm stateless across tool calls except what fits in context + what we wrote to disk." — one more area of research and feature for Kodand.

**Agreed:** Kodand *is* the fix. Before any `bun run`, the harness must `kodand recall --repo . --query "top unchecked task in FOCUS"` — not `cat` a file, but retrieval with ranking. This is the same `RCU/WAL` + `after_write` gate that gave `wildcard 0/24` vs `0.875` without guard: `FOCUS` as recallable intent, not chat history. Supermemory retrieves past chats; we retrieve current intent. New task `I9` in `IMPROVEMENTS.md` — auto-logged here per your rule (no prompt needed next time).
