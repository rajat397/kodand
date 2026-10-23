# Kill-test: OKF (Google Open Knowledge Format) as chunk schema

**What it is (authoritative):** Google OKF is a typed triple schema (entity, relation, value + provenance) for knowledge, not raw text. Designed for 10B+ facts, not 500 chats.

**Why it might help kodand:** Our `locator="session#i"` is a string; retrieval does BM25 on raw message text. OKF would type chunks (preference, event, temporal, relation) — `temporal-reasoning 0.50` and `single-preference 0.30` might gain from typed retrieval (filter by type, not just keywords). Local, deterministic.

**Kill criteria (brutal):** If OKF extraction needs an LLM per chunk (like supermemory's 40s/episode extraction) → KILL — we are offline, no API in retrieval. If typed schema doesn't lift `preference 0.30` on adv30 by +0.15 vs plain FTS in 5-min test → KILL.

**Test:** Same 30 adv30, same `nvidia/lightning` judge. One arm: current `chunkText = "[session date] role: content"`; other: `OKF-triples` generated offline via local `gemma2` (or rule-based) and indexed as `content + OKF JSON`. Measure `Hit@10` and accuracy on `single-preference` 8.

**Verdict so far:** NOT RUN — next after SPLADE.
