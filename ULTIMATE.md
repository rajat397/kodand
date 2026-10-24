# ULTIMATE — kodand as the one complete agentic/LLM memory

**Saved 2026-10-24 per owner: not stopping at repetition-rate/enforcement moat. Repetition is the wedge, complete is the destination.**

## The wedge vs the destination
- **Wedge (proven):** `bench/repeat` repetition-rate `0/24` via deterministic `after_write` hook `kodand/hooks/after_write.py` — the only thing no advisory memory can do. This is the entry wedge, not the product.
- **Destination:** one `bridge.db` that is the **entire** memory plane for an agent/LLM — not a recall plugin. Must subsume what supermemory/mem0/graphiti do *and* what they don't: staleness, enforcement, consolidation, privacy, cross-harness portability.

## What "complete" means — 5 planes (all local-first, all in one file)
1. **Episodic (what happened):** every session = `chunkText = [sessionId date]\nrole: content` `memorybench/src/providers/kodand/index.ts:45` + `ingested.json` resume cache, `WAL` + `FTS5 porter` `kodand/store/__init__.py:80`. Today: `Hit@10 0.75` full500, `adv30-syn3 3/20` after count-synth `index.ts:236`. Gap: semantic `porter` miss (`fitness classes` vs `Zumba`) — needs `sqlite-vec` 768d `embgemma2` real vectors (hash disabled `49a2b7e` for noise), `SPLADE/ColBERTv2` deferred `docs/kill-tests/*.md`.
2. **Semantic/OKF (what it means):** typed triples `type/entity/value` not raw text. Today: deterministic `like/including → baseMap` count synth for `how many` (`zumba 4→5` fixed `2788b940` correct). Next: `OKF.md` rule-based triples for `preference 0.30` and `temporal 0.50`, no LLM per chunk (unlike supermemory 40s/episode).
3. **Procedural (how to not repeat):** `promote(level)` artifacts `kodand/enforcement.py:29` → `hook/lint/test/ci` wired via `store.remember`, `memories.enforcement_level`, `check_write_content()` read-only + `hooks.after_write()` deny. Today: `0/24` on wildcard/hardcoded, `bench/repeat` deterministic grep grader.
4. **Governance (what stays fresh & safe):** `is_stale()` `kodand/validation.py:8` + `anchors (file,symbol,hash,commit)` `store/__init__.py:70` + `manifest` dep hash, `scope.py` secret shapes (entropy≥4.5) not words, `is_holdout` `utility.py:28` de-circularized, `swarm.py` atomic `claims(resource PK)` `BEGIN IMMEDIATE`. Missing: TTL per memory, conflict merge (STALE 55.2% implicit conflict).
5. **Portability (where it runs):** `kodand install opencode|claude-code|cursor|all` co-files `kodand.ts+lanes-guard.ts+rules-guard.ts` `kodand/kodand-plugin/install.sh`, `mcp` server, `bridge.db` single file, `KODAND_SKIP_SECRET=1` for data dirs. Missing: connectors, multimodal, profiles — explicitly non-goals this round `FOCUS.md:86` but required for complete.

## How this differs from graphify / supermemory fact-graph
| | Graph / supermemory | kodand complete |
|---|---|---|
| Extraction | LLM per episode (40s, cloud, $) | deterministic regex + `ast` + hash at `remember()` (<1ms, offline) |
| Store | vector DB + graph DB (two systems) | one `bridge.db` (`FTS5` + `vec0` + `hypervectors` `157×uint64` + `events` + `claims`) |
| Retrieval | vector+graph walk, then LLM | `bm25` → `COUNT` synth → `sqlite-vec` hybrid (weighted, not prepended) |
| Staleness | none (default never expires `docs.mem0 R6`) | `anchor.hash` compare, `validate_before_apply --strict` |
| Enforcement | advisory text | blocking artifact (hook exit≠0, lint, test) |
| Cost | $0.58/task C4, 17h/500Q ingest | $0, ~60s/500Q ingest, 1200ms search |

Graph wins at `1M chunks` multi-hop; we win at `how many` aggregation and at `0/24` enforcement. Complete = both: graph as **P1 HNSW** when `Hit@15 ≥0.85` proves need (per `IMPROVEMENTS.md:7`), not as P0.

## Deep-dive agenda for tomorrow (owner asked to save)
- [ ] **D1 — Define complete by workloads:** map every LongMemEval/LoCoMo/ConvoMem question type to plane 1-5, score kodand vs graph on each with `report-kodand-full500-nemotron.json` + `adv30-syn3` as baseline.
- [ ] **D2 — OKF schema v0.2:** finalize `type` enum (preference, event, temporal, relation) + `confidence` + `provenance` (session#i), decide `hypervectors` gate keeper vs reranker (reverted `16b0d2a` 0/20).
- [ ] **D3 — Staleness+TTL:** design `expiration_date` per memory (UTC) vs `anchor` hash — unify in read path, not write.
- [ ] **D4 — Consolidation:** `capture/mine_*` transcript correction → `intent` → `memory` lifecycle, `trust/surface` promotion, `utility = (avoided-caused)/exposures` with Laplace.
- [ ] **D5 — Scale gate:** when to flip `FTS15+synth` → `splade/colbert + LSM` — define `100k chunks` trigger, keep `WAL`+`bridge.db` portability.

## What we will NOT do
Chasing `97%` recall by adding cloud extraction — that replicates their cost. The `99% offline` target `FOCUS.md:65` stays: same harness, same `nvidia/lightning` judge, ` kodand-full500-count` (running `66903`) is the measuring stick, not a cloud side-by-side.

---
*This file is the north-star; `FOCUS.md` remains the 2-week scoreboard. Next commit updates FOCUS to point here.*
