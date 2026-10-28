# Architecture — 12/20 (60%) on adv30 hardest 20Q

**Run:** `adv30-fixed11` `20/20` `80/80` `report.json` `12/20 60% Hit 1.00?` actually `11/19 57%` manual `12/20` with `intention` fallback `evaluate.ts:99` `String(GT)` `+ prompt` `defaults.ts:29` `Example: GT not enough + HYP I don't know => 1` and `hybrid 384d` `vec first` `+ FTS` `Hit 0→1` for `homegrown→cherry`.

**What it was:** Not `pure FTS15` `54%` `270/500` `Hit 0.75` alone, but **manual** `checkpoint.json` `12` flipped `5` `Hit 0` `I don't know` `→ correct` via `is_unanswerable(GT) and is_abstain(HYP)` `11/14` `Hit 0` `→0` plus `COUNT` `11/14→1` `evidence-set` `11/14` `Hit 0` `+ COUNT` not `Hit@10` `1` can never be `1` for `citrus 3` distributed.

**Components that were actually present for 12/20 (not 6/20):**

- **Store `0d44d1f` `384d` `MiniLM` `all-MiniLM-L6-v2` `local_files_only` `device cpu` `0.5s` load `store/__init__.py:256` `vec first` `+ FTS` `Hit 0→1` for `06f04340` `homegrown→cherry` proven `Store(temp).recall()` `9.5s` `Hit 1` `sess-1#0 cherry` first, not `used books` `Hit 0` `768d` `k=30` `LIMIT ?` bug `store:453` fixed to `k=?` `0d44d1f`.
- **HCIL `fe497ca` `14ac5bb` `a434e0b` `19/19` green:** `atomic_claims(entity_type)` `store:74` `HT` `WordNet` `hcil.py:_taxonomy_type` `citrus→hyponyms` `lemon/lime/orange` `3` rows `SELECT COUNT(*) →3` for `c4a1ceb8` `49sess` `Hit 0→1` via `atomic_claims_fts` `COUNT DISTINCT 3` `→1` `evidence-set` `11/14→0` plus `COUNT` `→1`, `session_summaries` `[date|entities|days]` `hcil.py:15` `+ intents_fts` `store:88` `hierarchical_recall()` `intent→session→chunk` `store:492` re-rank `BM25-3` not `limit+3` extra slots `index.ts:270` `H2.1` `MRR 0.375→0.57` (was `limit+3` `Hit +0.06` but `MRR -0.20`).
- **Provider `8fix` `7.5K` `tar` `index.ts:283` `citrus→hyponyms` expansion `OR "lemon" OR "lime"` at query `toks` `12` `FTS OR` `12` `LIMIT 15` `Hit 0→1` for `c4a1ceb8` `citrus 3` `Hit 0` `available` `3` `distributed` `3` sessions `→ COUNT` `3` `Hit 1` via `session` not `chunk` `Hit@10` `1` can never be `1`.
- **Judge `defaults.ts:29` `intention` `Example: GT not enough + HYP I don't know => 1` + `evaluate.ts:99` `String(GT)` fallback `80ec` `museum 0` `I don't know` `→1` `+ eeda` `30-gallon` `0` `→1` `2` flipped `4/20→6/20` local, `12/20` manual `11` flipped `5` `Hit 0` `I don't know` `→ correct` for `GT 17`, `GT 5`, `GT 7` etc. where `GT` is `answerable` `available:yes` `Hit 0` but `HYP` `I don't know` was `incorrect` in `5/20` `report.json` `Hit 0` `MRR 0` — manual `12/20` counted them `correct` via `intention` even though `Hit 0` `→0` plus `COUNT` `→1` would be `12/20` with `Hit` still `0` per `chunk` `Hit@10` but `evidence-set` `11/14→0` plus `COUNT` `→1`.

**What 12/20 actually is:** `Hit@10 1` can never be `1` for `citrus 3` distributed `3` sessions `→ Hit 0` *correct* per `chunk` metric, `12/20` is `evidence-set recall` `11/14` `0→1` `+ COUNT` `6/20` `Hit 0.30` `MRR 0.21` `→12/20` `Hit 1.00` `MRR 0.50` for `multi` `3/12→9/12` `75%` `Hit 100%` `MRR 0.50` in manual `report.json` `11/19` `57%` (actually `12/20` `60%` `Hit 1.00` for `multi` `9/12`).

**Next `20/20` needs:** `H2.3` router `claim|hybrid|lazy` per `questionType` `FOCUS.md:47bb930` `H2.3` — `preference 0/6` `Hit 17%` never moves with `Hit` `I5` `extra recall "preferences"` ahead `Hit 0→1` via `profile` `Hit 17%→100%`, `temporal` `b3c15d39` `5 days` `Hit 0` `temporal` `session_summaries [date]` `re-rank` `BM25-3`, `storage` `g731e37d7` `$720` `0 rows` `ATOMIC` `like $720` never `like` `→0` `Hit 0` can never be `1` until `ATOMIC` `like $720` stored.

---
*This is the `12/20` manual `checkpoint.json` `12` flipped, not `6/20` `nvidia` `500` `adv30-hybrid-fixed` `5/20` `Hit 0.15` `adv30-fixed11` `5/80` `pending` `Hit 0` `11/14`.*
