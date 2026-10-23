# Improvements — from 54% toward supermemory's 95% (same harness, same judge)

**Goal:** close the 21pp retrieval gap (75→95 Hit@K) that caps accuracy, without touching model/ingest cost. Each task has acceptance in the harness.

## P0 — must before next 500

* **I1: Retrieval @15 + aggregation for multi-session (closes ~0.37→0.55).** Change `kodand-provider` search `limit 10 → 15` and add cross-session dedup+concat (merge top hits from same haystack into one context block). Accept: `kodand-full500` Hit@10 0.75 → Hit@15 ≥0.85 on the same 500, multi-session 0.37→≥0.50.
  * File: `memorybench/src/providers/kodand/index.ts:182` (`limit || 10`), `kodand/recall` top-K param.
* **I2: Rerank top-15 with cheap cross-encoder (MRR 0.57→0.70).** Add `bge-reranker` or `colbert` local (Xenova, already cached in `.supermemory/models` 105M) after FTS. Accept: MRR +0.10 on 500, no extra API calls.
  * File: `memorybench/src/providers/kodand/index.ts` search post-process.

## P1 — next tranche

* **I3: Temporal stitching (0.50→0.65).** Chunk with `+1 neighbor message` window and prepend `Date:` already stored in `chunkText` — include it in FTS indexed content (currently `content` only, locator holds date). Accept: temporal-reasoning +0.10.
* **I4: Assistant vs user salience (0.62→0.74).** Boost `assistant:` chunks with `locator` field weight in FTS5 (`content, locator` already indexed) — query expansion `assistant:` prefix. Accept: assistant 0.62→0.70.
* **I5: Preference profile (0.30→0.50).** Add `supermemory`-style user-profile cache: one `kodand recall --query "preferences"` ahead of every answer, prepend as system context. Accept: single-preference +0.15.
* **I6: Context tokens 3342→~2000.** Longer contexts hurt gemini-lite accuracy (F2 3078tok vs smoke 2490tok). Cap to `1200` tokens after rerank (truncate lowest-score chunks). Accept: tokens -30% with accuracy flat or up.

## P2 — harness

* **I7: Supermemory full500 on same Nemotron.** Run `supermemory-full500` with `nvidia/nemotron-3.5-lightning-30b-a3b` (local server, same judge, same 500). Code: `memorybench` already has `src/providers/supermemory` + local `supermemory-server` on `:6767` with `GEMINI_API_KEY` for extraction. Blocked only by extraction queue (40s/episode). Accept: `report.json` alongside kodand's for same-run table.
* **I8: Fix init secret-filter for harness.** Done `kodand/install/__init__.py:218` (skip high-entropy repo name `c27434e8_abs`), but add `KODAND_SKIP_SECRET=1` flag for `init_repo` to make it explicit. Prevents future `ingest failed` stalls.
* **I9: Kodand as external memory for its builder (stateless amnesia) — NEW P0.** Dogfood Kodand on itself: before any `bun run`, `kodand recall --repo /home/rajat/kodand --query "top unchecked task in FOCUS"` must return the current FOCUS task; `scripts/enforce-adversarial.sh` now calls `kodand recall`, not `grep`, and `BLOCKED` if top task is `Literature sweep` but `ingest 500` is attempted. This is the same `after_write` gate that gave `0/24` on wildcard — applied to task drift. Accept: `bench/run-adv30.sh` blocked unless `docs/kill-tests/*.md` have `Verdict:`; drift from `sweep → ingest` impossible without `BLOCKED`.
* **I10: sqlite-vec + hypervectors + Gemma2 + OKF locally (99% complete local) — NEW P0.** Replace pure FTS with hybrid: `sqlite-vec` (vector, `sqlite` as DB) + `FTS5` (lexical) + `10k-D hypervectors` (`157×uint64`, `popcount` gate, `Hillock` pattern, `~1.2GB` VRAM) + `embgemma2` local for RAG + `OKF` typed triples. All offline, one `bridge.db`. Accept: `adv30` `Hit 0.15→0.85` with `embgemma2` vectors, hypervector gate blocks hallucination before token gen, `OKF` fixes `preference 0.30` as typed profile.

## Non-goals this tranche

* Connectors, multimodal, cloud, compliance — not measured here.
* Model upgrade alone (GPT-4o judge) — harness already pins `nvidia` for both sides; accuracy delta from retrieval is larger than model delta (F2 gemini 60% vs full500 nemotron 54% = -6pp model effect vs -21pp retrieval gap).

**Order:** I1 → I2 → rerun `kodand-full500` on same model → if Hit@15 ≥0.85, run I3-I6; I7 runs in parallel once server is up (separate quota pool).
