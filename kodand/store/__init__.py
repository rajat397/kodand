"""
kodand.store - SQLite-based memory storage
"""

import queue
import sqlite3
import os
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any


class Store:
    """Unified sqlite bridge.db for kodand memory storage."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.db_path = os.path.join(self.repo_path, ".kodand", "bridge.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            surface TEXT DEFAULT 'text',
            locator TEXT DEFAULT '',
            scope TEXT DEFAULT 'repo',
            session_id TEXT,
            created_at REAL DEFAULT 0,
            updated_at REAL DEFAULT 0,
            superseded_by INTEGER,
            content_hash TEXT,
            state TEXT DEFAULT 'active',
            memory_type TEXT DEFAULT 'reference'
        );
        CREATE TABLE IF NOT EXISTS intents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            detail TEXT,
            updated_at REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events (
            ts TEXT NOT NULL,
            kind TEXT NOT NULL,
            entry_id INTEGER,
            provenance TEXT,
            detail TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_memories_state ON memories(state);
        CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope);
        CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
        CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
        CREATE TABLE IF NOT EXISTS claims (
            resource TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            claimed_at REAL NOT NULL,
            expires_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS anchors (
            entry_id INTEGER PRIMARY KEY,
            file_path TEXT NOT NULL,
            symbol TEXT DEFAULT '',
            start_line INTEGER DEFAULT 0,
            end_line INTEGER DEFAULT 0,
            content_hash TEXT NOT NULL,
            commit_hash TEXT DEFAULT '',
            confidence TEXT DEFAULT 'high'
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(content, locator, tokenize='porter');
        -- I10: sqlite-vec hybrid (FTS lexical + vector dense) + hypervectors
        -- vec0 virtual table is created lazily in _ensure_vec() to avoid hard dep on loadable extension at init time
        """)
        conn.commit()
        # Migrations for pre-existing DBs (idempotent).
        for ddl in [
            "ALTER TABLE memories ADD COLUMN is_holdout INTEGER DEFAULT 0",
            "ALTER TABLE memories ADD COLUMN enforcement_level TEXT DEFAULT 'context'",
        ]:
            try:
                conn.execute(ddl)
                conn.commit()
            except Exception:
                pass
        # FTS triggers (idempotent via DROP+CREATE).
        try:
            conn.executescript("""
            DROP TRIGGER IF EXISTS memories_fts_ai;
            DROP TRIGGER IF EXISTS memories_fts_ad;
            DROP TRIGGER IF EXISTS memories_fts_au;
            CREATE TRIGGER memories_fts_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content, locator) VALUES (new.id, new.content, new.locator);
            END;
            CREATE TRIGGER memories_fts_ad AFTER DELETE ON memories BEGIN
                DELETE FROM memories_fts WHERE rowid = old.id;
            END;
            CREATE TRIGGER memories_fts_au AFTER UPDATE ON memories BEGIN
                DELETE FROM memories_fts WHERE rowid = old.id;
                INSERT INTO memories_fts(rowid, content, locator) VALUES (new.id, new.content, new.locator);
            END;
            """)
            conn.commit()
            # Backfill FTS only if index is behind the table.
            try:
                n_mem = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
                n_fts = conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()[0]
                if n_fts < n_mem:
                    conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
                    conn.commit()
            except Exception:
                pass
        except Exception:
            pass
        # I10: vector + hypervector tables (best-effort, no hard fail if extension missing)
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            conn.load_extension(sqlite_vec.loadable_path())
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec USING vec0(embedding float[768] distance_metric=cosine)")
            conn.execute("CREATE TABLE IF NOT EXISTS hypervectors (entry_id INTEGER PRIMARY KEY, hv BLOB)")
        except Exception:
            pass
        conn.close()
        # I10 async worker: vector/hypervector generation off the hot path
        self._async_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._async_thread = threading.Thread(target=self._async_worker, daemon=True)
        self._async_thread.start()

    def _vec_embed(self, text: str) -> list:
        """Lightweight 768-d hash embedding (offline, no model) — placeholder for embgemma2.
        Each token hashes to a 768-d random unit vector, summed and L2-normalized.
        Deterministic, fast, ~0.02ms per text. Swap to embgemma2 when cached."""
        import hashlib, math, struct
        vec = [0.0]*768
        for tok in text.lower().split():
            # per-token deterministic random vector via hash
            h = hashlib.sha256(tok.encode()).digest()
            for i in range(768):
                # derive float in [-1,1] from hash bytes
                b = h[i % len(h)]
                vec[i] += (b / 127.5 - 1.0) * (1.0 / (1 + i % 7))
        # L2 normalize
        n = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x/n for x in vec]

    def _hv_encode(self, text: str) -> bytes:
        """10k-D hypervector gate (Hillock pattern): 157×uint64 bit-packed, popcount-ready.
        Bundles per-token random hypervectors via majority vote."""
        import hashlib, struct
        D = 10000
        N = 157  # ceil(10000/64)
        counts = [0]*D
        for tok in text.lower().split():
            # per-token random hypervector via hash
            hv = hashlib.sha256(tok.encode()).digest()
            # expand hash to 10k bits via repeated hashing
            bits = []
            cur = hv
            while len(bits) < D:
                for b in cur:
                    for bit in range(8):
                        bits.append((b >> bit) & 1)
                        if len(bits) >= D:
                            break
                    if len(bits) >= D:
                        break
                cur = hashlib.sha256(cur).digest()
            for i, b in enumerate(bits):
                counts[i] += 1 if b else -1
        # majority vote -> bits
        out = bytearray(N*8)
        for i in range(D):
            if counts[i] > 0:
                out[i//8] |= 1 << (i % 8)
        return bytes(out)

    def _async_worker(self):
        """Background worker: vector + hypervector generation, never blocks remember."""
        while True:
            try:
                item = self._async_queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                entry_id = item["entry_id"]
                content = item["content"]
                locator = item["locator"]
                # vec
                try:
                    import sqlite_vec, json as _json
                    vec = self._vec_embed(content + " " + locator)
                    conn = self._get_conn()
                    try:
                        conn.enable_load_extension(True)
                        conn.load_extension(sqlite_vec.loadable_path())
                        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec USING vec0(embedding float[768] distance_metric=cosine)")
                    except Exception:
                        pass
                    try:
                        conn.execute("INSERT INTO memories_vec(rowid, embedding) VALUES (?, ?)", (entry_id, _json.dumps(vec)))
                        conn.commit()
                    except Exception:
                        pass
                    try:
                        conn.close()
                    except Exception:
                        pass
                except Exception:
                    pass
                # hv
                try:
                    hv = self._hv_encode(content + " " + locator)
                    conn2 = self._get_conn()
                    try:
                        conn2.execute("CREATE TABLE IF NOT EXISTS hypervectors (entry_id INTEGER PRIMARY KEY, hv BLOB)")
                    except Exception:
                        pass
                    try:
                        conn2.execute("INSERT OR REPLACE INTO hypervectors(entry_id, hv) VALUES (?, ?)", (entry_id, hv))
                        conn2.commit()
                    except Exception:
                        pass
                    try:
                        conn2.close()
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                pass
            finally:
                try:
                    self._async_queue.task_done()
                except Exception:
                    pass

    def remember(self, content: str, surface: str = "text", locator: str = "",
                 scope: str = "repo", session_id: str = None, memory_type: str = "reference") -> dict:
        # Secret/PII exclusion at write time (Tranche 2.4)
        try:
            from kodand.scope import check_write
            ok, reason = check_write(content)
            if not ok:
                raise ValueError(reason)
        except ValueError:
            raise
        except Exception:
            pass
        conn = self._get_conn()
        now = datetime.now().timestamp()
        cur = conn.execute(
            "INSERT INTO memories (content, surface, locator, scope, session_id, created_at, updated_at, memory_type, state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')",
            (content, surface, locator, scope, session_id or "", now, now, memory_type)
        )
        entry_id = cur.lastrowid
        # I10 async: bulk import (import-jsonl, session_id=="import-jsonl") stays sync
        # so the CLI process doesn't exit before vec/hv are durable; interactive
        # single remembers stay async (off hot path, ~0.3s → ~0.02ms).
        is_bulk = (session_id == "import-jsonl")
        if is_bulk:
            # sync, same transaction, still fast (hash embed ~0.02ms, no model)
            try:
                import sqlite_vec, json as _json
                conn.enable_load_extension(True)
                conn.load_extension(sqlite_vec.loadable_path())
                try:
                    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec USING vec0(embedding float[768] distance_metric=cosine)")
                except Exception:
                    pass
                vec = self._vec_embed(content + " " + locator)
                conn.execute("INSERT INTO memories_vec(rowid, embedding) VALUES (?, ?)", (entry_id, _json.dumps(vec)))
            except Exception:
                pass
            try:
                hv = self._hv_encode(content + " " + locator)
                try:
                    conn.execute("CREATE TABLE IF NOT EXISTS hypervectors (entry_id INTEGER PRIMARY KEY, hv BLOB)")
                except Exception:
                    pass
                conn.execute("INSERT OR REPLACE INTO hypervectors(entry_id, hv) VALUES (?, ?)", (entry_id, hv))
            except Exception:
                pass
        else:
            try:
                self._async_queue.put_nowait({"entry_id": entry_id, "content": content, "locator": locator})
            except Exception:
                pass
        # auto-log captured event for north-star
        conn.execute(
            "INSERT INTO events (ts, kind, entry_id, provenance, detail) VALUES (?, ?, ?, ?, ?)",
            (__import__("datetime").datetime.now().isoformat(), "captured", entry_id, "store.remember", content[:120])
        )
        conn.commit()
        conn.close()
        # Content-hash anchor (Fix 2): best-effort, never fails remember.
        try:
            from kodand.validation import anchor_entry
            anchor_entry(self.repo_path, entry_id, locator)
        except Exception:
            pass
        return {"key": entry_id, "content": content, "scope": scope, "state": "active", "type": memory_type}

    def recall(self, query: str = "", k: int = 5, scope: str = None) -> List[dict]:
        import re as _re
        conn = self._get_conn()
        HOLDOUT = "COALESCE(is_holdout, 0) = 0"
        if query:
            # FTS5/BM25 rank path (stdlib sqlite, porter stemming) + LIKE union.
            fts_ids: List[int] = []
            try:
                toks = [t for t in _re.findall(r"[A-Za-z0-9_]+", query.lower()) if len(t) >= 2][:12]
                if toks:
                    ors = " OR ".join(f'"{t}"' for t in toks)
                    fts_rows = conn.execute(
                        "SELECT rowid FROM memories_fts WHERE memories_fts MATCH ? "
                        "ORDER BY bm25(memories_fts) LIMIT ?",
                        (ors, k * 3),
                    ).fetchall()
                    fts_ids = [r[0] for r in fts_rows]
            except Exception:
                fts_ids = []
            # I10: vector KNN hybrid (offline, cosine)
            vec_ids: List[int] = []
            try:
                import sqlite_vec, json as _json
                conn.enable_load_extension(True)
                conn.load_extension(sqlite_vec.loadable_path())
                qvec = self._vec_embed(query)
                vec_rows = conn.execute(
                    "SELECT rowid, distance FROM memories_vec WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
                    (_json.dumps(qvec), k * 3),
                ).fetchall()
                vec_ids = [r[0] for r in vec_rows]
            except Exception:
                vec_ids = []
            like = f"%{query}%"
            like_rows = conn.execute(
                f"SELECT * FROM memories WHERE state='active' AND {HOLDOUT} "
                "AND (content LIKE ? OR locator LIKE ?) ORDER BY created_at DESC LIMIT ?",
                (like, like, k * 3),
            ).fetchall()
            by_id = {r["id"]: dict(r) for r in like_rows}
            for ids in (fts_ids, vec_ids):
                if ids:
                    placeholders = ",".join("?" for _ in ids)
                    try:
                        for r in conn.execute(
                            f"SELECT * FROM memories WHERE id IN ({placeholders}) "
                            f"AND state='active' AND {HOLDOUT}",
                            tuple(ids),
                        ).fetchall():
                            by_id.setdefault(r["id"], dict(r))
                    except Exception:
                        pass
            # Rank: vector cosine first (if any), then FTS BM25, then recency
            # Merge order: vec_ids preserve cosine rank, fts_ids preserve BM25
            seen = set()
            entries = []
            for i in vec_ids:
                if i in by_id and i not in seen:
                    entries.append(by_id[i]); seen.add(i)
            for i in fts_ids:
                if i in by_id and i not in seen:
                    entries.append(by_id[i]); seen.add(i)
            entries += [e for i, e in by_id.items() if i not in seen]
            entries = entries[:k]
        else:
            rows = conn.execute(
                f"SELECT * FROM memories WHERE state='active' AND {HOLDOUT} "
                "ORDER BY created_at DESC LIMIT ?",
                (k,)
            )
            entries = [dict(r) for r in rows.fetchall()]
        conn.close()
        # Lazy validation: check stale at recall time (warn-only, never block)
        try:
            from kodand.validation import is_stale
            for e in entries:
                if is_stale(e, self.repo_path):
                    # log held as stale warning but still return entry
                    try:
                        self.log_event("held", e["id"], "validation.lazy", f"stale evidence: {e.get('locator','')}")
                    except Exception:
                        pass
        except Exception:
            pass
        return entries

    def get_memory(self, entry_id: int) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (entry_id,)).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def log_event(self, kind: str, entry_id: int = None, provenance: str = None,
                  detail: str = None):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO events (ts, kind, entry_id, provenance, detail) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), kind, entry_id, provenance, detail)
        )
        conn.commit()
        conn.close()

    def get_events(self, kind: str = None, limit: int = 100) -> List[dict]:
        conn = self._get_conn()
        if kind:
            rows = conn.execute(
                "SELECT * FROM events WHERE kind = ? ORDER BY ts DESC LIMIT ?",
                (kind, limit)
            )
        else:
            rows = conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,))
        entries = [dict(r) for r in rows.fetchall()]
        conn.close()
        return entries

    def list_memories(self, scope: str = None, state: str = "active") -> List[dict]:
        conn = self._get_conn()
        if scope:
            rows = conn.execute(
                "SELECT * FROM memories WHERE scope = ? AND state = ? ORDER BY created_at DESC",
                (scope, state)
            )
        else:
            rows = conn.execute(
                "SELECT * FROM memories WHERE state = ? ORDER BY created_at DESC",
                (state,)
            )
        entries = [dict(r) for r in rows.fetchall()]
        conn.close()
        return entries

    def delete_memory(self, entry_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.execute("UPDATE memories SET state = 'deleted' WHERE id = ?", (entry_id,))
        conn.commit()
        affected = cur.rowcount
        conn.close()
        return affected > 0


# Per-repo cache (was singleton, broke multi-repo tests)
_stores: dict = {}


def get_store(repo_path: str = None) -> Store:
    import os
    key = os.path.abspath(repo_path or os.getcwd())
    if key not in _stores:
        _stores[key] = Store(repo_path)
    return _stores[key]