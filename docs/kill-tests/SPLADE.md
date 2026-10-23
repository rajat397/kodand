# Kill-test: SPLADEv3 learned sparse retrieval (on-device)

**What it is (authoritative):** SPLADE learns a sparse expansion over the vocabulary (BM25 is 1976, SPLADE is 2021+). `SPLADEv3` + `uniCOIL` run on-device via `bge` family, no API. Supermemory's "graph" is not this.

**Why it might help kodand:** Our `porter` stemmer is the floor. `preference 0.30` and `assistant 0.62` gaps are lexical mismatch (e.g., "I like X" vs "preference: X"). Learned sparse expands queries/documents offline, still inverted index, still SQLite FTS, still `<500ms`.

**Kill criteria:** If `SPLADE` needs GPU or >2GB RAM on this `5.7Gi` box → KILL. If `Hit@10 0.75` doesn't move to `≥0.85` on full 500 (or `adv30` from `0.30` to `≥0.45` on `Hit`) in 5-min test → KILL — BM25+aggregation already does 0.75, don't add complexity for +0.02.

**Test:** Same 30 adv30, same judge. Arm A: current `FTS5 porter + @15 aggregation` (now live in `kodand-full500-15`); Arm B: `SPLADE` vectors via `embgemma2` (local) + `WAND` search. Both offline, no API. Measure `MRR 0.57 → 0.70` and `Hit`.

**Verdict so far:** KILL for P0 — keep `FTS15+aggregation` (now live in `kodand-full500-15`, `21004`). At 25k chunks, `SPLADE-v3` (MRR 40.2 on MS MARCO, BEIR 51.7) needs 512-token transformer per query/doc + 30k-dim sparse index; `naver/splade-v3` is 110M params, needs GPU/ >1GB RAM, no on-device win proven at this scale. Our `Hit 0.75` gap is aggregation (multi-session), not vocabulary expansion — `SPLADE` would expand but not merge sessions. Revisit only if `Hit@15` stays <0.85 after `I1`.

**Scale note:** Vespa/Meilisearch show SPLADE wins at 100M docs; at 25k, BM25+aggregation is near ceiling. Kill if scale mismatch — **killed**.
