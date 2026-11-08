# DECISIONS LOG (all decisions from the kodand v0.1.0 -> v0.2.0 build)

Every decision cites its evidence. Nothing here was chosen by taste; incidents and
run reports are always available for verification, and names of alternatives rejected
are kept deliberately so the reasoning survives the authors.

## Product and packaging

- **D1 — core/laya split into pip extras** (setup.py, v0.2.0). Core (`pip install
  kodand`) stays zero-dependency because a sqlite FTS recall has real value and no
  torch install should be mandatory. Laya tier is opt-in `pip install kodand[laya]`.
  Evidence: fresh-venv install verified; plain recall works (returns `[]` on empty).
- **D2 — `kodand fetch-model` with sha256 verification** (kodand/fetch_model.py).
  The ~644 MB checkpoint downloads into `~/.kodand/models/laya-multilingual`; a
  corrupted/partial file fails loudly, never passes silently. Files cached are
  re-verified in ~8 s even before rerank (checksum 9d628fd9…7f204e).
- **D3 — portable model lookup order**: `$KODAND_LAYA_MODEL` → `~/.kodand/models/...`
  → legacy `/mnt/...` (dev box, kept for continuity). Removal of the hard-coded
  early path is what allows pip users to run rerank (rerank.py `_default_model_dir`).
- **D4 — v0.2.0 wheel verified in an isolated venv** before tagging; enforces a
  distribution gate rather than trust in "it imports on the box".

## Retrieval and ranking

- **D5 — relative ranking, never absolute thresholds.** Probability is NOT calibrated
  across questions (an adversarial gold can read 0.35 while a standard non-gold reads
  0.095); absolute-threshold arms of the sweep measured 0.458–0.505 recall vs 0.520
  baseline, i.e., strictly worse. reject: `P >= 0.5 keep` forever. Incident: the
  M5 budget sweep + adv20 source runs.
- **D6 — session granularity, not chunk collapse.** The original chunk-mode rerank
  (1 best chunk per session) measured 188/500 - a context-starvation regression that
  ended the "shrink the set" family of levers. evidence: data/runs/kodand-full500-laya
  (+ report) and the "session-rank-not-drop" rule in rerank.py.
- **D7 — hybrid rank as shipped default (BM25 6 seeds + laya 4 fills, chunk budget 10)**
  after the E2M5-hybrid full run: accuracy 284/500 (best measured), coverage non-inferior
  except the small-type tail. Evidence: experiments/c-hybrid-full500-result.md,
  data/runs/kodand-full500-hybrid-H64-archive/report.json (committed copy).
- **D8 — budget (keep_sessions 8→10) is a dead lever; do NOT spend on it again.** Both
  arms B8 == B10 exactly on every measured question; chunk budget binds, not session
  budget. Incident: experiments/m5-budget-sweep-result.md.
- **D9 — 400-char scoring length is the production default** (A/B verified quality-equal
  to 800 on stratified subsets, half the latency); 250-char is rejected after measured
  quality loss on adversarial sets. Incident: ab400 measurements
  (`mnt/data/laya/ab400_scores.json`).

## Metric honesty

- **D10 — epoch discipline.** All published numbers carry an epoch label (LLM-judged
  epoch-1 vs deterministic evidence epoch-2); no mixed tables. Incident: the M5 metric
  reset identified that only epoch-2 metrics could be re-created without paid runs
  (memorybench tests `tests/session-evidence.test.ts`).
- **D11 — Option A (answer accuracy as primary) declared after the measured escalation
  ended** (h46 +8 futile); evidence recall stays a diagnostic with its known small-type
  cost (growth `55330f4`). LongMemEval full-runs are FROZEN until deep-roots K1-K5 land
  (growth experiments/deep-roots-track.md).
- **D12 — every hit-recall claim cites the run report path in its own report** (audit
  rule, not hope): baseline 0.8623 vs hybrid 0.8250 recorded with paths in the growth
  ledger and README sections.

## Safety

- **D13 — secrets never cross the write boundary**, with provider-shaped key
  constructors (sk-ant-, sk-proj-, generic `api_key =`) in scope.py after round-1 gaps
  were found in the detector list (tests/test_safety.py::test_anthropic_keys_blocked).
- **D14 — prompt-injection corpus + scanner ship in the distribution**
  (bench/safety/injection-corpus.json, 32 prompts×4 categories; scanner zero-hit gates).
- **D15 — kill switch $KODAND_BASELINE=1 shall always remain**: one env var reverts to
  FTS; the acceptance test proves p95=113 ms fallback and that no laya dial happens
  (docs/adapters/tests/smoke.py + tests/test_assemble.py::gate4).
- **D16 — we never execute recalled text as instructions** (contract text is identical
  in tests and README "What kodand does NOT do").

## Storage / lifecycle / artifacts

- **D17 — memory lifecycle is write-time** (Store.supersede / Store.correct with
  logged provenance); read-time recency heuristics were measured useless (M3 recency
  screen FAILED: 0 wins/1 loss) and retired as a lever.
- **D18 — artifacts are content-addressed, immutable versions, not mutable rows**
  ([uri, sha256]); editing a file creates a NEW version; the OLD chunks are superseded
  via D17 automatically (tests/test_artifacts.py::test_edited_artifact_supersedes).
- **D19 — every artifact chunk carries the provenance prefix in its own content:**
  `[artifact:<path>@<sha>]` so the grounded-answer contract (K1) can cite WHERE evidence
  came from, not only what it says.
- **D20 — image/text-less artifacts still get a memory row**: caption chunk with
  provenance, never silently dropped (tests/test_artifacts.py::test_image_artifact...).

## Contract with the stateless-LLM reality

- **D21 — per-chunk provenance lands in the question context itself (sessionId +
  entryId in every row)**; without that, citation-based debugging is impossible and
  conflicts have no anchor (K1 in memorybench).
- **D22 — answers must cite sources, and contradictions must be resolved by date, not
  averaged** (CITATION_CONTRACT); insufficiency becomes an explicit "I don't know" with
  sources: none (tests/citation-contract.test.ts).
- **D23 — cache-aware assembly (K4)**: memory context arrives as content-addressed,
  append-only blocks with a FROZEN slot table held by the caller (state file), plus a
  byte-stable prefix hash. Changing prefix mid-session is a hard error, not a warning
  (tests/test_assemble.py::test_prefix_shift_is_a_hard_error). Blocks never re-sort
  after first emission (append-only rule), so provider caches stay warm.
- **D24 — adapters resolve the freeze semantics, not the memory module**: the slot
  table lives in the caller-owned state file (a file per session), keeping kodand core
  stateless and mockable.

## Governance

- **D25 — every lever in this project needs a pre-registered gate before any run**,
  and every gate has a documented kill state. Recorded kills: M3 recency (gate FAILED:
  0 wins/1 loss), M5 budget sweep (B8==B10 both PASS but no-op), H46 ratio tweak (+0.0104
  subset-only), accuracy Optimization loop (frozen by D11 until K1-K5 land).
- **D26 — the growth work folder is single-source for goal truth**, doctrine updates
  and evidence; updates in code accompany an entry there. `git log` in the growth
  folder shows the register for every decision taken above.

## K5 memory surface

- **D27 — the surface is only allowed to render store truth**: the approved design's
  static sample rows would have made G1 pass with stale data (the browser test caught
  this), so every row is rendered FROM `/api/*` (nothing hardcoded; a databreak
  makes rows disappear, never fake a pass).
- **D28 — UI corrections map 1:1 to the store contract**: the correction modal posts
  {content, replaces_id} and hits Store.correct(origin='user') with event logging on
  disk; a supersede action routes to Store.supersede. There is no client-side state
  machine pretending — sqlite rows ARE the states.
- **D29 — verification style: a headless browser user session is the gate**
  (tests/verify_k5.py via Playwright): search, typed correction, save/dismiss with
  keyboard Escape (G5 escape-routes per design system), supersede through the live row
  action, screenshots per stage. Mock-based checks are forbidden as adequate proof
  after the G1 incident.
- **D30 — assembly openness is a product-surface property (G3)**: the surface explains
  "what the agent will read next" with K4 block ids/slots from the same assembly
  engine, not a parallel preview.

## First-principles spine (operator-enforced standing rule)

- **D31 — THE FIRST-PRINCIPLES SPINE (enforced at every step)** — operator directive
  2026-11-08: before building (or gluing) anything, the registered artifact for that
  step must show, in order: (1) the root-cause problem from first principles with
  observed triggers and the cost of leaving it unsolved; (2) a survey of the best
  mechanisms in existing solutions for THAT problem (named competitors and prior art,
  worth-taking pieces with trade-offs); (3) a derivation from the problem's own
  properties to our mechanism — any tech choice without a derivation footnote fails
  review; (4) ground-up build valued over glue; glue is allowed only where the
  ground-up route was tried AND failed (failure recorded beside it); (5) every
  step's outputs are checked against this spine — standups, critiques, and reviews
  examine the derivation before results.

Enforcement mechanics: the rule text lives in the growth ledger
(`~/growth/experiments/memory-problem-first-principles.md`, "GOVERNING RULE" section)
and the growth-runs agent definition carries the checklist so every activation sees
it; standups and /critique apply it to every registered step. First application of
the spine: decision #1 (hybrid spine + first-principles graph semantics, growth
`c63f452` and its derivation reply).

## Question surface (opencode-native) — deep dive, verified 2026-11-08

- **D33 — decisions must reach the operator through opencode's own question surface**,
  never as a markdown wall. Verified against the binary strings + installed SDK
  (v1.18.35) + plugin typings:

  1. The TUI has a **native `question` tool** (binary tool-table confirms
     `question:{...}` rendering + `question.asked/replied/rejected` events). We
     used it earlier in-session (the `/critique` bar) and got the actual popup.
  2. `QuestionInfo` schema: `{question, header (<=30, used as popup title),
     options:[{label, description}], multiple?, custom?}` — **exactly the shape
     the operator wants** (context + 4-5 label options + recommended + custom).
  3. HTTP fallback lives on the TUI's local server:
     - `LIST /api/session/{sessionID}/question` (pending)
     - `POST /api/session/{sessionID}/question/{requestID}/reply` and `/reject`
     The TUI's own instance is bound to an unnamed unix-socket inode (checked;
     fd 30/34 are anonymous), so "hit it from outside" is not the right route.
  4. The durable answer: **register a plugin tool backed by the plugin SDK** that
     posts a `QuestionRequest` through the TUI server (sdk v2
     `session.question`), in-process, so a popup occurs even when the model's
     own toolset starves the built-in `question` tool mid-session (this sat at
     the turn where we noticed it, plugin tools are always resolvable).
  5. Plugin contract confirmed in `@opencode-ai/plugin/dist/tool.d.ts`:
     `ToolDefinition{description, args(zod), execute(args, ctx)}` — our fallback
     tool is `growth_question({question, header, options[], multiple?})` posting
     to `POST /api/session/{sessionID}/question` (serverUrl comes free via
     `PluginInput.serverUrl`), and blocking on `GET .../question` until answered.

Enforcement: growth-runs agent definition amended to prefer the native tool and
fall back to the plugin tool (both popup-level); numbered-text-only as a last
resort. Implementation task registered: plugin `growth-question.ts` (one file,
~40 lines) shipping with the growth-runs agent.
