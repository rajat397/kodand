# FOCUS — Kodand as the one complete local memory plane

**North star `ULTIMATE.md`:** repetition `0/24` is wedge, not ceiling. One `bridge.db` `WAL` that is the entire memory plane — episodic + semantic + procedural + governance + portability — complete local, no cloud LLM per episode. Graph is a derived view, not the brain (`BEYOND_GRAPH.md` HCIL vs flat entity graph).

## Scoreboard — accuracy + validity + token (same harness/judge or it doesn't count `FOCUS:Rules`)

| # | Claim | Source | Our target | Current `report.json` |
|---|---|---|---|---|
| C1 | LongMemEval-S 97% R@20 (GPT-4o) | supermemory.ai | `Hit@10 0.85` + `MRR 0.57→0.65` on same `nvidia/lightning` 500Q | `Hit 0.75→0.81` `hcil6`, `MRR 0.574→0.375` (re-rank bug) |
| C2 | 95% R@15 @720 tok (99.4% cut) | README | `MemScore triple` not acc alone | `54%/1563ms/3342tok` → `53%/3984ms/3452tok` `full500-hcil` `+111 tok` for `+0.06 Hit` |
| C3 | LoCoMo #1, ConvoMem #1 | research | run both, report | deferred to P1 after `Hit@15≥0.85` |
| C4 | SWE-Context 30% tasks $0.58/task | independent | `≥ fail-to-pass` + `repetition 0/24` second axis | `0/24` via `after_write` `kodand/hooks` holds |
| C5/C6 | 200-300ms search | docs | `≤500ms` local sqlite | `1563→3984ms` (+2.5× `hierarchical_recall` spawns) — fix batch |
| **V1** | Stale rate 19.4%→10.9% (P-Mem) | `arxiv` P-Mem | `≤10.9%` on `knowledge-update` `STALE` 1.2k Q | `71.8% vs 75.6%` on KU, no TTL yet |
| **V2** | Retraction recovery | P-Mem | recoverable where CRUD lost | `causal_links` `store:74` exists, not probed |
| **V3** | Trust: 50.2% false authority | `arxiv` | `trust×conf×prov` semiring, no untrusted supersede | `entropy≥4.5` `scope.py` only, no trust propagation |

## Completed (numbers pasted, not claimed)

- [x] **F1 provider `src/providers/kodand/`** `DONE 2026-10-20` — `FTS5 porter` pure, `Hit 0.75` baseline `270/500 54%` `report-kodand-full500-nemotron.json` 7.4M. Bugs fixed: recency tiebreak `MRR 0.00→0.574`.
- [x] **F2 10Q 60% / F3 149Q 51.7% / F3 full500 54%** — abstention-heavy, `multi 0.37` `preference 0.30` were named gaps.
- [x] **Pivot 2026-10-23 + HCIL skeleton `0e3ca8c` `19/19` green** — `intents(intents_fts)` `session_summaries_fts` `okf_triples` `causal_links` `store/__init__.py:44` + `hcil.py` deterministic `<1ms` `summarize_session([date|entities|days])` + `hierarchical_recall()` `intent→session→chunk`.
- [x] **Adv30 hardest 20Q:** `syn3 3/20 Hit 0.30 MRR 0.21` (count `4→5` baseMap) `> hcil6 4/20 Hit 0.30 MRR 0.12` `> hcil5/4 2/20` `> hcil 0/20` — `count+ledger+session limit+3` `index.ts:270` finally beat pure on hardest slice without `Hit` displacement.
- [x] **TUI harness** `d1b3c8e` — `bench/retrieval-dump/full500-hcil.json 6.9M` `500Q` frozen `Hit 0.81`, `scripts/dump-search.mjs` now reads `report.json` `evaluations.searchResults`, `bench/TUI_ANSWER_GUIDE.md` decouples `Hit/MRR` (index+search) from `accuracy` (model reasoning) — any TUI session can `answer-dump` same retrieval with different model.

## Roadmap — 3 horizons, pick task by task

### Horizon 1: Write-path correctness (P0, carries architecture — Lemmalog+P-Mem bottleneck: extraction+canonicalization)

- [ ] **H1.1 Atomic claims, schema-aware iterative extraction** — `store self-contained claims not triples, staged validation, raw immutable` `hcil.py:20` `like X,Y` → `okf_triples(subject,predicate,object,confidence)` + `valid_time` field. *Why:* biggest limiter per your research (write corruption). *Files:* `hcil.py`, `store:okf_triples`. *Accept:* `adv30` extractor `never emitted` cases drop `>30%` on 20Q hardest, no new tokens. *Depends:* none.

- [ ] **H1.2 Bitemporal qualified statements** — `valid_time + transaction_time + who + trust` per claim, replaces `isLatest` flag. *Why:* n-ary facts + `STALE` `1.2k Q` implicit conflict `55.2%` best. *Files:* `store:okf_triples valid_time`, `anchors:commit_hash` is `transaction_time`. *Accept:* `knowledge-update 71.8%→≥75%` on `full500`, stale `≤10.9%`. *Depends:* `H1.1`.

- [ ] **H1.3 Trust semiring** `trust×conf×prov` on `intents_fts` + `causal_links` — untrusted observation can't supersede trusted value (`50.2%` false authority). *Why:* P-Mem limit. *Files:* `store:intents correction trust`, `scope.py`. *Accept:* `unauthorized supersede 0/20` on `P-Mem` trust probe. *Depends:* `H1.2`.

### Horizon 2: Retrieval & reasoning (P0, derived view)

- [ ] **H2.1 Hybrid late-interaction + cross-encoder reranker** — `ColBERT` multi-vector keeps token detail `single-vector compresses` + `cross-encoder` re-rank top-30. *Why:* `MRR 0.574→0.375` drop when `Hit 0.75→0.81` — ranking is bug, not recall. *Files:* `memorybench/src/providers/kodand/index.ts:search` re-rank not extra slots (was `limit+3` `HIT -0.20`). *Accept:* `MRR 0.375→0.57` with `Hit 0.81` held, `search 3984→1563ms` (batch to one `python`). *Depends:* none, gates `SPLADE` P1.

- [ ] **H2.2 Lazy query-time relation discovery + cache** — keep `memories` raw, discover `like` relations when asked, cache validated `causal_links`. Graph becomes cache. *Why:* write-time `like` extraction compounds errors. *Files:* `hcil.py:extract_okf` called at `search` not `ingest`. *Accept:* `adv30` `Hit 0.30` held with `+0` ingest ms. *Depends:* `H1.1`.

- [ ] **H2.3 Learned router (outcome-trained)** — `claim lookup | rules | hybrid | lazy` per query, trained on `answer correctness` not similarity (prompted LLM router only recovers `2/3` gain per P-Mem). *Why:* `preference 30%` needs profile cache not `FTS`, `multi` needs `COUNT`. *Files:* `index.ts:search` router, `bench/retrieval-dump` logs as training data. *Accept:* `preference 30%→50%` `I5` + `multi 36%→50%` without `Hit` loss. *Depends:* `H2.1`, `H2.2`.

### Horizon 3: Scale & completeness (P1, gate at 100k chunks)

- [ ] **H3.1 RAPTOR hierarchical summaries as index only** — `session_summaries` never source of truth, `1503eeb` `1d29fa8` deferred. *Files:* `store:session_summaries` already.
- [ ] **H3.2 HNSW + LSM for 1M** `sqlite-vec 768d` `76M/25k` `docs/kill-tests/SQLITE_VEC` `vec 0.20 MRR` revert `16b0d2a` — keep as P1 `BEYOND_GRAPH.md`, not now.
- [ ] **H3.3 Full500>54% with same `nvidia/lightning` judge** — `full500-hcil` `265/500 53%` is `Hit +0.06` but `MRR -0.20` + `+2421ms` search, so revert to re-rank fix `H2.1` before `SPLADE`.

## Rules

- Same harness `nvidia/nemotron-3.5-lightning-30b-a3b` pinned per run, `MemScore triple`, publish `report.json` `per-question results + failures`, `intents_fts` `session_summaries_fts` stay in `bridge.db` `WAL` single file.
- Fork **Lemmalog MIT** `github.com/JordyZomer/lemmalog` as `bench/lemmalog-baseline` for `102Q LongMemEval` + `LoCoMo` + `P-Mem` `revision/retraction` probes — don't rebuild Datalog, build `trust` on it.

## Non-goals (this horizon)

Connectors, multimodal, `Hopfield`/`VSA`/`Titans`/`TransE` per your research skip list — exactness/editability conflict.

---
*Next pick:* `H1.1` (atomic claims) or `H2.1` (re-rank `MRR`) — both unblock `H2.3` router. Tell me which, `gnhf --current-branch` with `8 iters 2M` will run it detached without `status` pings.*
