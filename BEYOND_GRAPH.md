# Beyond Graph — why flat entity graphs are not the ceiling for agentic memory

**Thesis:** Graphify / supermemory build a *fact graph* (entities → relations → facts). Agentic memory needs a *causal intent ledger* (intent → attempt → outcome → correction → enforcement). The second subsumes the first and is the only thing that compounds over time. Flat graphs don't learn.

## 1. What fact-graphs do well vs where they plateau

| Fact graph (supermemory, Graphiti, Mem0-graph) | Where it stalls for agents |
|---|---|
| LLM extracts `Person —likes→ Blue` per episode (40s, cloud) | No *why* or *so what*: `likes Blue` is trivia, not `tried Blue theme → user corrected to dark → blocked light theme via hook` |
| Hybrid `vector + graph walk` lifts `Recall@20 97%` on LongMemEval-S (their paper) | `how many` still fails: graph lists 4 classes but doesn't count `Zumba Tue+Thu =2` — needs deterministic `COUNT` not walk (`adv30-syn2 0/20 → adv30-syn3 3/20` after our count synth) |
| Entities deduped, relations typed | No **staleness**: default `never expires` (`R6` Mem0 expiry opt-in), no `anchor(file:symbol:hash:commit)` like `kodand/store/__init__.py:70` + `validation.py:8` |
| One graph per user, grows monotonically | No **consolidation**: 500 sessions × 50 msgs = 25k rows → 2.5M at 10k files, graph walk becomes `10×` slower; no sleep-time summarization |
| Advisory: returns text for LLM to read | No **enforcement**: `0/24` repetition via `after_write` deny `kodand/hooks/after_write.py` is not in graph |

Evidence from this repo: `docs/kill-tests/SQLITE_VEC_HYPERVECTORS.md` — `vec 768d ×25k =76MB` fits, but `hypervector 10k-D` popcount hurt `MRR 0.574→0.20` (`16b0d2a` revert). Graph at 25k is overkill; at 1M it's needed but as **index**, not as brain.

## 2. Better than graph: Hierarchical Causal Intent Ledger (HCIL)

Inspired by human consolidation (episodic → semantic during sleep) and by control-plane vs data-plane.

```
Layer 3: INTENT (goal) ── "ship 99% offline recall"
    └─ Layer 2: EPISODE (session) ── [sessionId date] + neighbor window `index.ts:47`
          └─ Layer 1: CHUNK (message) ── FTS5 porter + vec0 (future embgemma2)
                └─ Layer 0: TRIPLE (OKF-lite) ── `like X, Y` → {zumba, hip hop abs} `index.ts:236`
                     └─ LEDGER: attempt → outcome → correction (from `capture/mine_*` + `opencode.db` transcript)
```

**Why hierarchical beats flat:**

1. **Compression:** daily job rolls `session` rows into `session_summary` (one row per session, ~100 tokens) — keeps `bridge.db` single file, `WAL`, no second DB. Graph stores every entity edge forever; we store **summaries + ledger**, not every phone number.

2. **Causal edges, not entity edges:** `intent: "avoid bare-except"` → `attempt: wrote except:` → `outcome: lint failed` → `correction: use except SpecificError` → `enforcement: tests/test_kodand_1.py` `enforcement.py:29`. This is a *policy* that compounds. Entity edge `Person —uses→ bare-except` is trivia.

3. **Deterministic where it matters:** `anchor(hash)` for staleness, `COUNT` for `how many`, `entropy≥4.5` for secrets `scope.py`. Graph would LLM-judge staleness (STALE 55.2% best `Gemini 3.1` — still coin-flip). Use hash, not judge.

4. **Enforcement as memory:** `swarm.py:42 claims(resource PK) BEGIN IMMEDIATE` is memory that *acts*. Graph returns text; ledger returns `BLOCKED: memory#1 says use X`.

5. **Profile as cache, not retrieval:** `I5` preference profile — one `recall "preferences"` ahead of every answer, prepended as system context. No graph walk, just `FTS` top-3 preferences. `single-preference 0.30` should lift to `0.50` with this alone.

## 3. What we keep from graph, what we replace

- **Keep when scale proves need:** `sqlite-vec` 768d cosine + `HNSW` for `1M chunks` (`I10`), `SPLADE` learned sparse for `BEIR 51.7` (`docs/kill-tests/SPLADE.md` — deferred to P1). That's the graph's *index* value, not its *ontology*.
- **Replace:** LLM per-episode extraction (40s) → deterministic `ast` + regex at `remember()` (<1ms). Entity graph → intent ledger + `events(kind)` table.
- **Add:** `temporal stitching +1 neighbor` `index.ts:47` (already shipped), `context cap 6000 chars` `index.ts:250` (ships with this doc), `holdout is_holdout` de-circularization `utility.py`.

## 4. How we prove it

- Same harness, same `nvidia/lightning` judge: `kodand-full500` 54% is baseline. `adv30-syn3` 15% is first ledger win (fitness). Next `adv30-I3I5I6` targets `temporal 0.50→0.65` + `preference 0.30→0.50` with **no cloud, no vector yet**.
- If `Hit@15 ≥0.85` not reached after I3-I6, we then add `embgemma2` vectors — that's the honest gate for graph-like index, not belief.

**Bottom line:** Don't build a better entity graph. Build a **memory that does work** — counts, blocks, expires, consolidates — with graph only as an index when `25k→1M` forces it. That's the complete solution `ULTIMATE.md` asks for.
