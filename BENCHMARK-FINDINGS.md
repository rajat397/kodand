# Benchmark Findings — kodand vs Supermemory (2026-10-23)

**Runs banked:** `kodand-full500` 500/500 `270/500 = 54%` (`nvidia/nemotron-3.5-lightning-30b-a3b` judge+answer, MemScore 54% / 1563ms / 3342tok, retrieval Hit@10 75% MRR 0.574). Previous: `kodand-f2` 10-Q 60% gemini-3.8, `kodand-f3c` 149/500 gemini-lite 51.7%. Artifacts: `~/memorybench/data/runs/kodand-full500/report.json` (7.4M) + `~/backups/report-kodand-full500-nemotron.json`.

## What works

* **Knowledge-update 59/78 (0.76) Hit 0.94, single-user 52/70 (0.74) Hit 0.93:** when evidence is in one chunk, FTS + bulk ingest is strong. No hallucination profile holds (abstain > confabulate).
* **Ingest/Search are code, not LLM:** per-message chunked `import-jsonl` (500 containers, 1 process/container, FTS5 porter, instant indexing) — `500/500 ingested` in ~1 min at concurrency 8 sequential, checkpointed. No model cost.
* **Deterministic staleness + enforcement:** content-hash anchors + `promote() → hook/lint/test/CI` + force-guard `0/24` on wildcard+hardcoded where memory-only repeats at `0.875`.

## What fails (measured, not guessed)

| Type | Accuracy | Hit@10 | Diagnosis |
|---|---|---|---|
| multi-session 49/133 (0.37) Hit 0.66 MRR 0.51 | lowest | evidence spread across sessions — top-10 chunks don't assemble the full picture (F2 already named this). Aggregation, not ranking. |
| single-preference 9/30 (0.30) Hit 0.63 | lowest | cheap model doesn't hold preferences across turns; retrieval mid (0.63) but answer collapses. Needs preference-profile, not just recall. |
| temporal-reasoning 66/133 (0.50) Hit 0.67 | mid | date-aware stitching weak (cross-session time). |
| assistant 35/56 (0.62) vs user 0.74 | gap | assistant facts less salient in FTS. |
* Overall: retrieval ceiling `75% Hit@10` vs supermemory claim `95% Recall@15` — `20pp` of accuracy is unreachable until retrieval moves.

## Why

* **Top-10 chunk limit:** multi-session questions need >10 evidence slices. Supermemory retrieves `Recall@15/20` with aggregation; we cap at 10 flat.
* **No aggregation/rerank:** FTS BM25 only, no cross-session merge, no reranker. MRR 0.574 → correct chunk is rank ~2-3 on average, but multi-session needs 2-3 chunks together.
* **Chunk = 1 message:** long messages split on message boundary only, not semantic. Temporal questions need windowed context.
* **Judge/model confound:** nemotron-lightning is reasoning model (no temp, needs longer timeout) — 1.5× slower than gemini-lite, but quota-free. Scores are model-pinned, not absolute.

## Supermemory pending

* Full compare `NOT RUN` — local server extraction is the slow pole (~40s/episode ×50 = ~35 min per question) and shares the same Gemini quota. Next `supermemory-full500` will run `nvidia/nemotron-3.5-lightning-30b-a3b` on `localhost:6767` (same model, same harness, apples-to-apples). Report stays separate column until then.
