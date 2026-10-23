# Kill-test: sqlite-vec + hypervectors + Gemma2 + OKF (complete local)

**What it is (authoritative):** `sqlite-vec` (sqlite as vector DB, `vec0` extension, pure `sqlite`, no Chroma) + `Hypervectors 10k-D` (`157×uint64`, `XOR+popcount`, `Hillock` pattern, `0.01ms` gate) + `embgemma2` (local `Xenova/bge-base-en-v1.5` 768d, already cached 105M) + `OKF` (Google markdown+YAML, `type` field only, `v0.2` trust signals).

**Why it might help kodand (99% complete local):** Current `FTS5 porter` is lexical only (`Hit 0.75`). `sqlite-vec` adds dense `768d` vectors in same `bridge.db` file (one file, `WAL`, no server). `Hypervectors` add late-interaction gate *before* LLM call (blocks hallucination if factual graph doesn't overlap query, like Hillock). `OKF` types `preference` vs `temporal` vs `event` (fixes `preference 0.30` as typed profile, not recall). All offline, `<1.2GB` VRAM, CPU `popcount` on `ARM NEON` (verified in Hillock).

**Kill criteria (brutal, scale-aware):** If `sqlite-vec` needs `>2GB` RAM at `25k` chunks → KILL (but `embgemma2` 768d × 25k = `76MB` + FTS, fits). If `hypervector` gate drops `recall` (Hit 0.75→0.60) for precision → KILL (we need `Hit 0.85`, not `0.60`). If `OKF` extraction needs LLM per chunk → KILL (rule-based triples only).

**Test:** Same `adv30` 20 Q, same `nvidia/lightning` judge, fully offline, no API. Arm A: `FTS15+aggregation` (baseline `Hit 0.75`); Arm B: `sqlite-vec + FTS5 hybrid` (`embgemma2` vectors) + `hypervector gate` + `OKF` typed filter. Measure `Hit@15`, `MRR`, `abstain` (gate should make `abstain` honest, not hallucinate). No `supermemory` re-run.

**Verdict so far:** NOT RUN — next after `SPLADE` DEFER. This is `I10` P0 for 99% complete local.

**Scale note:** At `largest repos` (`10k files`, `1M chunks`), `sqlite-vec` + `HNSW` + `LSM` is the `sub-300ms` path that beats hosted `supermemory` (network call vs file). Keep `sqlite` as single file, not Chroma.
