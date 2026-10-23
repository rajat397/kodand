# Kill-test: SPLADEv3 learned sparse retrieval (on-device)

**What it is (authoritative):** SPLADE learns a sparse expansion over the vocabulary (BM25 is 1976, SPLADE is 2021+). `SPLADEv3` + `uniCOIL` run on-device via `bge` family, no API. Supermemory's "graph" is not this.

**Why it might help kodand:** Our `porter` stemmer is the floor. `preference 0.30` and `assistant 0.62` gaps are lexical mismatch (e.g., "I like X" vs "preference: X"). Learned sparse expands queries/documents offline, still inverted index, still SQLite FTS, still `<500ms`.

**Kill criteria:** If `SPLADE` needs GPU or >2GB RAM on this `5.7Gi` box → KILL. If `Hit@10 0.75` doesn't move to `≥0.85` on full 500 (or `adv30` from `0.30` to `≥0.45` on `Hit`) in 5-min test → KILL — BM25+aggregation already does 0.75, don't add complexity for +0.02.

**Test:** Same 30 adv30, same judge. Arm A: current `FTS5 porter + @15 aggregation` (now live in `kodand-full500-15`); Arm B: `SPLADE` vectors via `embgemma2` (local) + `WAND` search. Both offline, no API. Measure `MRR 0.57 → 0.70` and `Hit`.

**Verdict so far:** NOT RUN — first kill-test to run (P0 before LSM/OKF). Model `embgemma2` already cached `nomic-embed-text` is dense, not SPLADE — need `SPLADE` weights.

**Scale note:** Best engineering blogs (e.g., Vespa/Meilisearch at 100M docs) show SPLADE wins at large scale with learned index; at 500×50=25k chunks, BM25 may already be near ceiling. Kill if scale mismatch.
