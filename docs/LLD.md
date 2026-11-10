# Kodand — Low-Level Design (LLD)

Details below mirror the code as of **v0.3.0** (tagged `ff90e77`). Where behavior is
measured, the numbers carry their source. Compare [HLD.md](HLD.md) for the system view.

## 1. Repository map

```
kodand/
  store/__init__.py        # Store: sqlite schema, remember/recall, lifecycle, events
  recall/__init__.py       # RecallEngine (utility-rerank on ties, prospective)
  rerank.py                # laya filter: score_sessions, rank_sessions, hybrid_rank, serve_tcp
  fetch_model.py           # checkpoint download + sha256 verify
  artifacts.py             # extraction + (uri,sha) registry + auto-supersede
  assemble.py              # K4 block emitter, frozen slot table
  surface.py               # K5 http surface (stdlib) + API routes
  scope.py                 # write-path secret/PII detector list (KEY_PATTERNS)
  capture/  hooks/  mcp/  install/   # harness surface
  cli/__init__.py          # argparse CLI: init/remember/recall/rerank/...
tests/                     # 82 tests (store, lifecycle, artifacts, assemble, safety, rerank, surface wiring)
bench/                     # adversarial-30.json, safety corpus, ENFORCE gate, reports
docs/                      # HLD/LLD/architecture, adapters, DECISIONS, memory surface html
```

## 2. Storage model (sqlite)

Single file per repo (`<repo>/.kodand/bridge.db` via `Store`). Key tables:

```sql
memories(id PK, content, surface, locator, scope, session_id,
         created_at, updated_at, superseded_by INTEGER NULL,
         content_hash, state TEXT DEFAULT 'active', memory_type, is_holdout)
memories_fts            -- FTS5 (porter) over content
memories_vec            -- sqlite-vec 384-d MiniLM embeddings (embeddings.py fallback)
intents / session_summaries / okf_triples / atomic_claims / causal_links
artifacts(id, uri, sha256, kind, size, extraction, n_chunks, created_at, UNIQUE(uri,sha256))
events(ts, kind, entry_id, provenance, detail)
```

State machine: `active` -> `superseded` (`superseded_by` points at the newer row).
`recall` reads only `state='active'`; `list_memories_with_supersede_chain(id)`
walks both directions for provenance.

## 3. Recall path (`Store.recall`)

1. **FTS5 BM25**: tokenized query (alnum tokens >= 2, max 12, OR-joined) against
   `memories_fts`, LIMIT k*3.
2. **Semantic**: sqlite-vec KNN in `memories_vec` (MiniLM 384-d via `sqlite_vec`
   extension; falls back silently to [] when lib/thread missing).
3. **LIKE union**: substring safety net over content/locator, newest first.
4. **Fusion order**: vec results first, then FTS, then LIKE leftovers, sliced to k.
5. **Lifestyle filters**: only `state='active'`, holdout excluded.
6. **Engine re-rank**: `RecallEngine.recall` reorders by utility score ONLY on ties,
   preserving FTS-derived order when no utility data exists (comment-batted in code).

Known measured shapes: warm daemon recall p50 0.08 s / p95 0.09 s
(docs/adapters/tests`smoke.py), CLI one-shot spawn ~10-16 s (python-import bound,
documetned in adapter doc).

## 4. laya rerank tier (`rerank.py`)

- `score_chunks(query, chunks)` -> adds `laya_p` per chunk (batch 8, 400-char texts).
- `score_sessions(query, chunks)` -> groups by `locator` '#session' prefix,joins
  up to 3 chunks as `session_text` (<= 700 chars), evaluations `noul` with instruction
  "This session would help answer the question: ..." (Q placed at the question-end
  marker - the formulation bugfix that made zero-shot rerank viable).
- `rank_sessions(query, chunks, keep_chunks=10)` -> sort by p-desc; per session the
  session's BM25-best chunks travel TOGETHER (multi-chunk evidence kept; the
  188/500 lesson lives here).
- `hybrid_rank(query, chunks, seed_slots=6, fill_slots=4)` -> BM25-deduped seed
  sessions + laya-scored fills beyond seeds; shipped default rank (284/500 epoch-1).
- `filter_sessions` / `filter_via_socket` -> the same judge as CLI/daemon variants.
- `serve_tcp(host=:8765)` -> ThreadingTCPServer; JSONL one-line req/resp: all rank
  modes dispatch on request "mode" ("sessions" | "hybrid" | "chunks").

## 5. Surface API (K5, `surface.py` + `docs/k5-memory-surface.html`)

| route | verb | body/params | returns |
|---|---|---|---|
| `/` | GET | - | approved k5 html (rendered from disk, G1 data truth) |
| `/api/ledger?q=` | GET | - | active + superseded rows (<=200), per-row supersede chains |
| `/api/artifacts` | GET | - | versioned artifact rows (uri, sha256, kind, size, n_chunks) |
| `/api/events?kind=` | GET | - | events journal (kinds: superseded, correction, artifact-ingested, captured) |
| `/api/assembly?q=` | GET | - | K4 blocks preview (ids, slots, prefix_hash) with a stable textual prefix |
| `/api/correct` | POST | `{content, replaces_id?}` | Store.correct(origin=user) + job event; 400 on empty content |
| `/api/supersede` | POST | `{entry_id, reason?}` | Store.supersede; 400 on already-superseded |

Verified end-to-end in `tests/verify_k5.py` (headless Playwright, screenshot
artifacts under /mnt/data/laya/k5-e2e/): G1-G5 gates with named lessons where the
G1 incident forced mock removal.

## 6. K4 assembler algorithm

```
block_id = sha256(text + provenance)[:16]        # content identity, never slot number
slots    = caller-owned state JSON: {block_id: slot, prefix: hash}
insert   = kind: icke existing -> slot = max(slots)+1 (append-only)
order    = blocks sorted by slot; text = prefix + blocks + question
invariant: prefix hash mutation between calls => RuntimeError (hard error)
```

Adapter states live in `~/.kodand/surface-assemble-<repoHash>.json` (the product
CLI `kodand assemble`) or in the adapters' own filesystem (the plugin).

## 7. Artifacts (K3)

`ingest_artifact(store, repo, path, caption)`:
1. abspath -> sha256 -> check `(uri, sha)` exists -> return `already-ingested`.
2. extract text: md/code plain; html via HTMLParser (script/style stripped);
   pdf via pypdf (extra `[pdf]`, friendly error); image -> caption-only row.
3. insert artifacts row, remember each <=800-char chunk with
   content prefix `[artifact:<abs path>@<sha>] ` and locator `artifact:<abs path>@<sha>#<n>`.
4. supersede previous-version chunks for the same uri (via K2 mechanism) incident
   `newer-artifact-version`.
5. log `artifact-ingested` event.

## 8. Safety (scope.py + bench/safety)

- Detector regex list: AWS `AKIA…16`, github token, slack, OpenAI `sk-[A-Za-z0-9]{20,}`,
  Anthropic `sk-ant-...`, `sk-proj-…`, PEM header, bearer token, generic
  `api_key = "..."` assignment. `check_write` fails any match or high-entropy
  token serialization, blocking in `Store.remember` AND in `import-jsonl`.
- bench/safety/scan_artifacts.py: `secrets` mode re-USES the same detector list over
  repository/sqlite/logs content (zero-hit gate; test fixtures excepted with reason).
- bench/safety/injection-corpus.json: 32 rows across 4 categories, size/categor
  assertions inside `corpus` mode.

## 9. CLI surface

Subjects (see `kodand/cli/__init__.py`): init, install, remember, recall, rerank,
rerank-server, rerank-serve, recalld, fetch-model, ingest-artifact, assemble,
memory-surface, mcp, capture-tick, capture-loop, doctor, anchor, manifest-watch,
import-jsonl, team/swarm/handoff/trust flows, utility, warm-start, handoff.

Env contract (all adapters honour):
- `KODAND_BASELINE=1`      - kill switch to FTS-only, bypasses laya entirely
- `KODAND_LAYA_URL/-KEEP/-POOL` - scoring server coordinate + session/chunk caps
- `KODAND_RECALL_URL`      - persistent recall daemon coordinate
- `KODAND_LAYA_MODEL`      - checkpoint override (otherwise portable ~/.kodand path)
- `KODAND_LAYA_SEEDS/-FILLS` - hybrid rank ratio
- `KODAND_LAYA_MAX_CHARS`  - per-chunk truncation control (default 400)

## 10. Measured characteristics (v0.3.0)

| metric | value | source |
|---|---|---|
| warm recall (daemon) | p50 0.08 s / p95 0.09 s | smoke.py |
| laya model load | 28-45 s once per proc | run logs (2026-10-31) |
| laya scoring (batch 8, 160-char) | 4.1 s | run20 probe |
| hybrid full-500 search latency | p50 39.8 s, p95 58 s (2-core, cold-loop) | kodand-full500-laya-sess report |
| test suite | 82 tests, ~30 s | `pytest -q` |
| accuracy (LongMemEval-500, identical judge) | 0.540 base -> 0.569 hybrid on 499 evaluated (+14, McNemar p=0.19, n.s.); sources: memorybench data/runs (external), summaries in bench/reports/runs/ | data/runs/kodand-full500-hybrid-H64-archive/report.json |

## 11. Known failure modes / edges (documented behavior)

- GPU empty envs raise documented errors with install hints (laya missing, pypdf missing).
- `assemble` refuses mutated prefixes (exit 3 at CLI, RuntimeError in library) by design.
- artifact ingest of an UNCHANGED file is a no-op; a CHANGED file supersedes chunks in K2,
  so stale chunks never surface (tests/test_artifacts.py::test_edited_...*).
- memory surface kills a stale assemble state only on prefix change; idempotent
  (identical request returns cached rows, no re-write).
- Windows azure unsupported? `ImportError` from sqlite-vec extension surfaced as a qery
  fallback (safe degrade), no hard-block.

## 12. Extension points

- additional `KEY_PATTERNS` detection shapes just need a tuple/enlist + tests.
- new artifact kinds registered in `_kind_of()` + `extract_text()`.
- new surface rows/views: any route that exposes one service method; tests are contract
  tests (data truth) not screenshot tests.
- new harness adapters: read `docs/adapter.md` - the stdout-contract and env vars are the
  entire interface.
