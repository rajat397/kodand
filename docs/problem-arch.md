# Product-Architecture: the locked problem set and the answer architecture

Stage-1 deliverable for the pre-registered experiment
`memory-problem-first-principles` (growth ledger, O1.2) — locked by the operator
2026-11-08. Numbers cite run reports; competitor cells are as-built facts.

## 1. The locked problem set (P1–P7)

| ID | problem (locked wording) | surfaced first via |
|---|---|---|
| P1 | Consolidation gap — sessions emit thousands of statements; nothing turns them into coherent, deduplicated, conflict-resolved state | mem0/letta comparison sessions |
| P2 | Temporal truth — facts are versioned and dependent; reads must resolve to the state true at turn t | knowledge-update regressions (epoch-1) |
| P3 | Trust weighting — statements differ in authority (user-correction > human-note > artifact > auto-capture > model inference) | hallucinated paraphrase beats typed correction |
| P4 | Window & cache economics — prompt layout must balance cache-warmth, staleness and bounded growth | latency/cost probes |
| P5 | Task-conditioned query semantics — agents need what matters for the task at hand, not top-k similarity | adversarial splits |
| P6 | Human authority loop — memory trusted only if inspectable and correctable | the k5 surface design |
| P7 | Self-curating memory — salience filter at capture + proactive surfacing at read, so the agent gets better at the user's real work without polluting prompts | operator-named (2026-11-08); 100s-of-sessions use case |

## 2. The answer architecture (decisions D1–D9, locked)

Each problem gets a mechanism derived from its own properties (spine rule D31):

| problem | mechanism | derived property | built? |
|---|---|---|---|
| P1 | **hybrid spine**: deterministic statement graph + local-model merge *proposals* (never auto-apply) | merge lends semantics; determinism owns truth | spine in K2 (supersede/correct); batch pending |
| P2 | **temporal genius read**: `get_state(entity, as-of-t)` over supersedes edges (recursive CTE, no graph db) | facts are versioned; reads are projections | planned (D3 build) |
| P3 | **authority strata** on the read path (user-correction > capture > artifact > model); recency inside class only | truth differs from relevance; class precedence, not a blended score | planned (D2 build) |
| P4 | **state-blocks-first assembly** + episodic tail; prefix stable; changes only on graph events | state IS current; episodic IS trailing evidence | planned (D4 v2) |
| P5 | **entity-state queries** over the same graph; no embeddings in state path; NER-grounded canonical keys | task questions are about entities, not docs | planned (D3 build) |
| P6 | **K5 surface cards + validity timeline** (graph later); every correction = journal event | human eyes are the audit loop | built v0.3.0; entity view planned |
| P7 | **salience tier at capture** (rule-first, laya-assist borderline) + **proactive surfacing** (prospective triggers over entity state, competing for D4 slots) | capture cheap/plentiful, context scarce | planned (first build item) |

## 3. Competitor matrix (rows = user problems, cells = as-built fact)

| dimension | mem0 | Letta/MemGPT | supermemory | claudemem | graphify/Graphiti | **kodand v0.3.0** |
|---|---|---|---|---|---|---|
| local/offline, no per-turn LLM cost | partial | partial | absent | partial | partial | **full** |
| provenance per fact | partial | partial | partial | absent | partial | **full** |
| authority: user correction wins structurally | absent | partial | absent | absent | partial | **full (write-time lifecycle)** |
| artifact version registry | absent | absent | partial | absent | absent | **full** |
| cache-aware prompt assembly | absent | absent | absent | absent | absent | **full** |
| semantic consolidation (LLM fusion) | **full** | partial | **full** | partial | absent | planned (D5) |
| temporal knowledge graph | partial | absent | absent | absent | **full** | planned (D3 layer) |
| visual correction loop | partial | partial | partial | absent | partial | **full (K5)** |

Planned ≠ claimed-as-built: the two "planned" rows are exactly the Q4 O1 pillars,
each pre-registered. Everything "full" is committed in-repo with tests.

## 4. Stage map (registered)

- **Stage 1 — problem set (DONE, this doc)**
- **Stage 2 — build (next)**: (1) P7 salience filter + D5 async worker;
  (2) D3 `statemap.get_state`; (3) D4 `assemble_v2`; (4) K5 entity view.
- **Stage 3 — dogfood**: ≥5 unique correction round-trips (D6 spec), memory
  surpasses baseline MEMORY.md (P7 recall hit gate).
- **Stage 4 — honest novelty statement**: every claim surviving review; no pushed
  moats; "planned" rows only claimed at ship.

## 5. Pre-registered gates (index)

D1 graph kinds · D2 authority tests (hallucination-loses) · D3 get_state correctness
· D4 state-block-first tests (byte-identical fallback) · D5 idempotence/freshness/
prefix-invariance/race/authority · D6 dogfood counts · D7 card→row data-truth ·
D8 matrix honesty · D9 lock-1 (this doc).
