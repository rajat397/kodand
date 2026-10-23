# Kill-test: LSM-tree for write-heavy ingest (classic CS, not ML)

**What it is (authoritative):** LSM-tree (LevelDB/RocksDB) — write-heavy ingest buffered in memtable, flushed as sorted SSTables, background compaction. Linux kernel `WAL` + `mmap` already in our `bridge.db` via SQLite WAL mode.

**Why it might help kodand:** `500 × 50 = 25k` chunks ingest via `import-jsonl` (1 process/container, 500 forks, ~1 min) is write-heavy. Current SQLite `FTS5` does synchronous trigger rebuilds per row. LSM would make `ingest 500/500` in seconds and keep `seen` cache + `ingested.json` marker from growing.

**Kill criteria:** If `ingest 500/500` is already <2 min (it is: `Bulk ingest stored=10-12` per batch, `ingest 500/500` in ~1 min at `concurrency 8`) → KILL — LSM is solving a solved problem. Also KILL if it needs a new storage engine (lose `WAL` + `FTS5` + `bridge.db` single-file portability).

**Test:** Measure `kodand-full500` ingest wall time (`500/500` in `mb-full500.log`) vs `kodand-full500-15` with current SQLite. If delta <10s → not worth it.

**Verdict so far:** LIKELY KILL — ingest is already not the bottleneck (answer/evaluate are, via LLM quota). Keep SQLite `WAL` + `seen` map (`memorybench/src/providers/kodand/index.ts:70`).

**Scale note:** LSM wins at 100M writes (Uber, RocksDB at Meta). At 25k rows, SQLite `FTS5` is the right scale. Learn the core idea (buffered writes, background merge) but don't verbatim adopt.
