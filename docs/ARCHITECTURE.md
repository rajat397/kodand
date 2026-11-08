# Kodand — Technical Architecture (in depth)

The three documents are a set: [README](../README.md) (product) ->
[HLD.md](HLD.md) (system) -> this file -> [LLD.md](LLD.md) (code) ->
[DECISIONS.md](DECISIONS.md) (why). Everything here reflects **as-built** code
at v0.3.0; anything aspirational is marked.

## 1. The problem architecture (root causes, not features)

LongMemEval-500 runs and real coding-agent sessions exposed three *structural* failure
classes that ranked-list retrieval cannot fix by tuning:

1. >80% session-evidence recall but answers still wrong -> the failure shifted
   to the *usage* of evidence (no citations, no conflict resolution, context
   churn invalidating caches + constancy).
2. Newer vs older versions of facts coexist -> ranking cannot express "this was
   retired"; needs write-time lifecycle state.
3. Sessions touch real artifacts (pdf/repos/md/HTML) that never enter memory,
   so "what did we learn about atlas.pdf" never becomes retrievable.

K1 (citation contract), K2 (lifecycle), K3 (artifact registry), K4 (block
assembly), K5 (surface) target these directly. Each has a dogfood-level gate,
pre-registered in the growth folder. Metric honesty: epo epochs (LLM-judged
epoch-1 vs evidence epoch-2) never mix (D10-D12).

## 2. Process & communication architecture

```
Coding agent harness (any)
 └── adapters (opencode plugin / CC hooks / raw pipe)
      │ shell + JSON-lines contract
      ▼
 ┌─ kodand core processes ─────────────────────────────┐
 │  kodand recalld (:8766)    read-side warm daemon    │
 │  kodand rerank-serve(:8765) side-side rank daemon   │  ← shared 830 MB laya model
 │  kodand memory-surface(:8881) human UI              │
 │  kodand mcp (stdio)        MCP server               │
 └─────────────────────────────────────────────────────┘
        │                │                 │
        ▼                ▼                 ▼
   <repo>/.kodand/bridge.db     ~/.kodand/models/laya-multilingual
   (FTS, vec, artifacts)        (sha-verified checkpoint)
```

- Loopback-only; no remote network. Kill switch `KODAND_BASELINE=1` at every
  entry (verified tests/test_assemble.py::gate4 + adapters smoke.py).
- Every daemon is `Restart=always` systemd user unit; observed 3 machine
  reboots were survived without data loss because of independent per-question
  checkpoints.

### 2.1 Data engineering details

- **Storage SQLite packaging**: one db per repo, so multi-team isolation is
  per-repository (multi-host sync explicitly N/A in v0.3.x).
- **Index packing**: memories_fts (porter tokenizer) + memories_vec (sqlite-vec
  MiniLM 384-d), both kept in sync inside `Store.remember` (same transaction).
- **Query planning**: BM25 prefilter LIMIT k*3 -> vec prefilter k*3 -> LIKE →
  union in vec > fts > like order; engine rerank utility only on ties.

### 2.2 The laya decision model (why a scoring head)

Non-generative: outputs a calibrated "would this session help answer Q"
probability in ~0.6-1.2 s per 400-char session on CPU; no tokenization of the
answer side, no chat completion cost. Load once per daemon boot (~30 s);
batched via `predict_batch` (one forward pass per 8 shards). The formulation
decided matters: **question text must sit at the question-end marker**
(`"This session would help answer the question: Q"`), sessions truncated to
400 chars each (validated against 800 QUALITY-equal, half the latency; 250-char
rejected on measured quality regressions).

### 2.3 The ranking architecture (lesson-earned, not tuned)

```
BM25 order (harness-trust baseline)  ─┐
                                       ├─ hybrid_rank: 6 BM25 seeds
session scorer p (laya)             ─┘  + 4 laya fills (recency-band aware)
                                       → budget 10 chunks, sessions never collapse
```

Errors that drove this design (keep, they are lessons): chunk-collapse dropped
to 188/500; recency gate failed 0 wins/1 loss; budget 8->10 is a no-op; ratio
tweak ~0.0104 std didn't generalize. History in `experiments/*-result.md`.

### 2.4 K4 assembly: why content-addressed blocks survive caches

- block ids hash `(text + provenance)`, slot tables are caller-held, append-only.
- prefix hash bytes: `sha256(prefix)`. Two successive assemble calls with the
  same prefix produce identical `assembled_sha256` tests — provider caches hit.
- prefix mutation mid-session is a hard RuntimeError (fresh session needed).

### 2.5 Surface + human-in-loop safety

- rows overlay approved design; corrections/supersede write-backs land as
  resources (events journal + sqlite state machine) with `provenance=user`
  (highest trust). Locked: user edits outrank anything model-written.
- read layer is stdlib HTTP; screenshots from the Playwright verify run
  (`tests/verify_k5.py`, screenshot dir in artifacts).

### 2.6 Safety pattern

- **Write blockers** with detector-shape fail-closed logic inside the Store.
- **Scanner gates** reuse the SAME detector list to prove no detectors leak
  content to disk (bench/safety/scan_artifacts.py; zero-hit with fixture
  exceptions commented inline).
- **Injection corpus test suite** runs with `corpus` mode pre-checks.
- **Human corrections** (surface + harness adapters) are the quality loop:
  origin-weighted provenance, motion to re-generate ratios later.

## 3. Cross-cutting invariants

| invariant | enforcement |
|---|---|
| local recall offline | no network calls in the recall path; fetch-model only triggers on demand |
| bounded model memory | single laya daemon, sha-checked weights; core CLI never imports torch (import test in fresh venv) |
| kill switch everywhere | env checked in providers, daemons, and assembly layer |
| provenance precision | every row carries sessionId + entryId; artifacts carry uri@sha |
| never execute memory | recall returns strings, never tool-dispatch — enforced by read-only JSON contract |
| honesty | README table references runs; DECISIONS log cites evidence per decision |

## 4. Test architecture

- **unit**: lifecycle/artifacts/assemble/safety/rerank gates (python sqlite temp
  dirs; fake a gent objects injected (no model loads in CI)
- **integration CLI**: subprocess tests against `kodand` CLI real binary
- **contract (eth)**: memorybench `cite` tests asserting emitted prompts
- **browser (ui)**: headless Playwright human-like session, screenshots as
  artifacts, gated by k5 gates files (found a G1 mock bug and the 'modal label
  case-sensitive' bug — both now recorded tests)

### 4.1 perf budget on this hardware

- AMD Ryzen 3 3250U, 2 cores, 5.8 GB. The full benchmark run saturates both
  cores when reranking 30-40 candidates; per-runnable latency stats in LLD §10.
- measured: laya ~830 MB; recalld ~50 MB; renderer ~150 MB; as a rule of thumb
  we keep the *surface* UI light (stdlib; no React) on purpose.

## 5. Extension protocol

Any new capability follows the registered-gate recipe at
`experiments/deep-roots-track.md`:
1. pre-register the gate (numbers, falsifiable condition)
2. implement with tests (unit + integration; no benchmark dependency)
3. record the verdict — every killed class recorded with numbers
4. growth ledger + DECISIONS.md appended with evidence

## 6. Road beyond v0.3.0 (frozen unless dogfood demands)

- M4 async fast path (TTFM < 2s on the 2-core box via recalld-only FTS first
  token path; long verification deferred until dogfood week)
- dogfood week (~M7): numeric gates: > = = 5 logged correction-events with
  timestamps; measured via events journal
- coverage rework *only if* dogfood shows evidence matters to real sessions
