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
            updated_at REAL DEFAULT 0,
            parent_id INTEGER REFERENCES intents(id),
            attempt TEXT DEFAULT '',
            outcome TEXT DEFAULT '',
            correction TEXT DEFAULT '',
            enforcement_ref TEXT DEFAULT ''
        );
        -- HCIL: hierarchical ledger extensions
        CREATE TABLE IF NOT EXISTS session_summaries (
            session_id TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            intent_id INTEGER REFERENCES intents(id),
            msg_count INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS okf_triples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER REFERENCES memories(id),
            session_id TEXT,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            created_at REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS atomic_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER REFERENCES memories(id),
            session_id TEXT,
            claim_text TEXT NOT NULL,
            subject TEXT, predicate TEXT, object TEXT,
            valid_time TEXT, transaction_time REAL, confidence REAL,
            source_hash TEXT
        );
        CREATE TABLE IF NOT EXISTS causal_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intent_id INTEGER REFERENCES intents(id) NOT NULL,
            from_entry_id INTEGER REFERENCES memories(id),
            to_entry_id INTEGER REFERENCES memories(id),
            relation TEXT NOT NULL, -- attempt|outcome|correction|enforcement
            created_at REAL DEFAULT 0
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
        CREATE INDEX IF NOT EXISTS idx_session_summaries_intent ON session_summaries(intent_id);
        CREATE INDEX IF NOT EXISTS idx_okf_session ON okf_triples(session_id);
        CREATE INDEX IF NOT EXISTS idx_okf_subject ON okf_triples(subject);
        CREATE INDEX IF NOT EXISTS idx_atomic_session ON atomic_claims(session_id);
        CREATE INDEX IF NOT EXISTS idx_atomic_subject ON atomic_claims(subject);
        CREATE INDEX IF NOT EXISTS idx_causal_intent ON causal_links(intent_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS session_summaries_fts USING fts5(summary, session_id, tokenize='porter');
        CREATE VIRTUAL TABLE IF NOT EXISTS intents_fts USING fts5(summary, detail, correction, tokenize='porter');
        CREATE VIRTUAL TABLE IF NOT EXISTS atomic_claims_fts USING fts5(claim_text, session_id, subject, object, tokenize='porter');
        -- I10: sqlite-vec hybrid (FTS lexical + vector dense) + hypervectors
        -- vec0 virtual table is created lazily in _ensure_vec() to avoid hard dep on loadable extension at init time
        """)
        conn.commit()
        # Migrations for pre-existing DBs (idempotent).
        for ddl in [
            "ALTER TABLE memories ADD COLUMN is_holdout INTEGER DEFAULT 0",
            "ALTER TABLE memories ADD COLUMN enforcement_level TEXT DEFAULT 'context'",
            "ALTER TABLE intents ADD COLUMN parent_id INTEGER REFERENCES intents(id)",
            "ALTER TABLE intents ADD COLUMN attempt TEXT DEFAULT ''",
            "ALTER TABLE intents ADD COLUMN outcome TEXT DEFAULT ''",
            "ALTER TABLE intents ADD COLUMN correction TEXT DEFAULT ''",
            "ALTER TABLE intents ADD COLUMN enforcement_ref TEXT DEFAULT ''"
        ]:
            try:
                conn.execute(ddl)
                conn.commit()
            except Exception:
                pass

        # FTS triggers for session_summaries + intents
        try:
            conn.executescript("""
            DROP TRIGGER IF EXISTS session_summaries_fts_ai;
            DROP TRIGGER IF EXISTS session_summaries_fts_ad;
            DROP TRIGGER IF EXISTS session_summaries_fts_au;
            CREATE TRIGGER session_summaries_fts_ai AFTER INSERT ON session_summaries BEGIN
                INSERT INTO session_summaries_fts(rowid, summary, session_id) VALUES (new.rowid, new.summary, new.session_id);
            END;
            CREATE TRIGGER session_summaries_fts_ad AFTER DELETE ON session_summaries BEGIN
                DELETE FROM session_summaries_fts WHERE rowid = old.rowid;
            END;
            CREATE TRIGGER session_summaries_fts_au AFTER UPDATE ON session_summaries BEGIN
                DELETE FROM session_summaries_fts WHERE rowid = old.rowid;
                INSERT INTO session_summaries_fts(rowid, summary, session_id) VALUES (new.rowid, new.summary, new.session_id);
            END;
            DROP TRIGGER IF EXISTS intents_fts_ai;
            DROP TRIGGER IF EXISTS intents_fts_ad;
            DROP TRIGGER IF EXISTS intents_fts_au;
            CREATE TRIGGER intents_fts_ai AFTER INSERT ON intents BEGIN
                INSERT INTO intents_fts(rowid, summary, detail, correction) VALUES (new.id, new.summary, new.detail, new.correction);
            END;
            CREATE TRIGGER intents_fts_ad AFTER DELETE ON intents BEGIN
                DELETE FROM intents_fts WHERE rowid = old.id;
            END;
            CREATE TRIGGER intents_fts_au AFTER UPDATE ON intents BEGIN
                DELETE FROM intents_fts WHERE rowid = old.id;
                INSERT INTO intents_fts(rowid, summary, detail, correction) VALUES (new.id, new.summary, new.detail, new.correction);
            END;
            DROP TRIGGER IF EXISTS atomic_claims_fts_ai;
            DROP TRIGGER IF EXISTS atomic_claims_fts_ad;
            DROP TRIGGER IF EXISTS atomic_claims_fts_au;
            CREATE TRIGGER atomic_claims_fts_ai AFTER INSERT ON atomic_claims BEGIN
                INSERT INTO atomic_claims_fts(rowid, claim_text, session_id, subject, object) VALUES (new.id, new.claim_text, new.session_id, new.subject, new.object);
            END;
            CREATE TRIGGER atomic_claims_fts_ad AFTER DELETE ON atomic_claims BEGIN
                DELETE FROM atomic_claims_fts WHERE rowid = old.id;
            END;
            CREATE TRIGGER atomic_claims_fts_au AFTER UPDATE ON atomic_claims BEGIN
                DELETE FROM atomic_claims_fts WHERE rowid = old.id;
                INSERT INTO atomic_claims_fts(rowid, claim_text, session_id, subject, object) VALUES (new.id, new.claim_text, new.session_id, new.subject, new.object);
            END;
            """)
            conn.commit()
            # Migration for atomic_claims_fts schema change (add session_id)
            try:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(atomic_claims_fts)").fetchall()]
                if "session_id" not in cols:
                    conn.execute("DROP TABLE IF EXISTS atomic_claims_fts")
                    conn.execute("CREATE VIRTUAL TABLE atomic_claims_fts USING fts5(claim_text, session_id, subject, object, tokenize='porter')")
                    conn.executescript("""
                    DROP TRIGGER IF EXISTS atomic_claims_fts_ai;
                    DROP TRIGGER IF EXISTS atomic_claims_fts_ad;
                    DROP TRIGGER IF EXISTS atomic_claims_fts_au;
                    CREATE TRIGGER atomic_claims_fts_ai AFTER INSERT ON atomic_claims BEGIN
                        INSERT INTO atomic_claims_fts(rowid, claim_text, session_id, subject, object) VALUES (new.id, new.claim_text, new.session_id, new.subject, new.object);
                    END;
                    CREATE TRIGGER atomic_claims_fts_ad AFTER DELETE ON atomic_claims BEGIN
                        DELETE FROM atomic_claims_fts WHERE rowid = old.id;
                    END;
                    CREATE TRIGGER atomic_claims_fts_au AFTER UPDATE ON atomic_claims BEGIN
                        DELETE FROM atomic_claims_fts WHERE rowid = old.id;
                        INSERT INTO atomic_claims_fts(rowid, claim_text, session_id, subject, object) VALUES (new.id, new.claim_text, new.session_id, new.subject, new.object);
                    END;
                    """)
                    conn.execute("INSERT INTO atomic_claims_fts(atomic_claims_fts) VALUES('rebuild')")
                    conn.commit()
            except Exception:
                pass
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
        # I10 disabled: vec/hv off hot path (random hash + 10k-D caused 10s hangs and rank noise).
        # Re-enable only with real embgemma2 + weighted fusion.
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
            # I10: vector KNN hybrid disabled for now — hash embed was random and
            # dominated FTS rank (vec first). Re-enable only with real embgemma2
            # and weighted fusion. Keep empty list so FTS is the sole ranker.
            vec_ids: List[int] = []
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
            # Rank: pure FTS BM25 (vec disabled) — preserve BM25 order, fallback recency
            seen = set()
            entries = []
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

    # ── HCIL: Hierarchical Causal Intent Ledger ──
    def create_intent(self, summary: str, detail: str = "", parent_id: int = None,
                      attempt: str = "", outcome: str = "", correction: str = "", enforcement_ref: str = "") -> dict:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO intents (summary, detail, parent_id, attempt, outcome, correction, enforcement_ref, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (summary, detail, parent_id, attempt, outcome, correction, enforcement_ref, datetime.now().timestamp())
        )
        iid = cur.lastrowid
        conn.commit()
        conn.close()
        self.log_event("intent_created", iid, "hcil", summary[:120])
        return {"id": iid, "summary": summary, "parent_id": parent_id}

    def get_intent(self, intent_id: int) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM intents WHERE id=?", (intent_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def list_intents(self, status: str = None) -> List[dict]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM intents ORDER BY updated_at DESC").fetchall() if not status else conn.execute("SELECT * FROM intents WHERE status=? ORDER BY updated_at DESC", (status,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def record_causal(self, intent_id: int, relation: str, from_entry_id: int = None, to_entry_id: int = None) -> dict:
        conn = self._get_conn()
        cur = conn.execute("INSERT INTO causal_links (intent_id, from_entry_id, to_entry_id, relation, created_at) VALUES (?, ?, ?, ?, ?)",
                           (intent_id, from_entry_id, to_entry_id, relation, datetime.now().timestamp()))
        cid = cur.lastrowid
        conn.commit()
        conn.close()
        return {"id": cid, "intent_id": intent_id, "relation": relation}

    def upsert_session_summary(self, session_id: str, summary: str, intent_id: int = None, msg_count: int = 0) -> dict:
        conn = self._get_conn()
        conn.execute("INSERT OR REPLACE INTO session_summaries (session_id, summary, intent_id, msg_count, created_at) VALUES (?, ?, ?, ?, ?)",
                     (session_id, summary, intent_id, msg_count, datetime.now().timestamp()))
        conn.commit()
        conn.close()
        return {"session_id": session_id, "summary": summary}

    def get_session_summary(self, session_id: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM session_summaries WHERE session_id=?", (session_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def add_okf_triple(self, entry_id: int, session_id: str, subject: str, predicate: str, obj: str, confidence: float = 1.0) -> dict:
        conn = self._get_conn()
        cur = conn.execute("INSERT INTO okf_triples (entry_id, session_id, subject, predicate, object, confidence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (entry_id, session_id, subject, predicate, obj, confidence, datetime.now().timestamp()))
        tid = cur.lastrowid
        conn.commit()
        conn.close()
        return {"id": tid}

    def add_atomic_claim(self, entry_id: int, session_id: str, claim_text: str, subject: str = "", predicate: str = "", obj: str = "", valid_time: str = "", confidence: float = 0.9) -> dict:
        import hashlib
        h = hashlib.sha256(claim_text.encode()).hexdigest()[:12]
        conn = self._get_conn()
        cur = conn.execute("INSERT INTO atomic_claims (entry_id, session_id, claim_text, subject, predicate, object, valid_time, transaction_time, confidence, source_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (entry_id, session_id, claim_text, subject, predicate, obj, valid_time, datetime.now().timestamp(), confidence, h))
        cid = cur.lastrowid
        conn.commit()
        conn.close()
        return {"id": cid, "claim_text": claim_text}

    def hierarchical_recall(self, query: str, k: int = 5) -> List[dict]:
        """Intent → session_summary → chunk fallback. Returns chunks with `hcil_level` tag."""
        # 1. intent level: FTS over intents_fts (not LIKE)
        conn = self._get_conn()
        intents = []
        try:
            import re as _re2
            toks = [t for t in _re2.findall(r"[A-Za-z0-9_]+", query.lower()) if len(t) >= 3][:6]
            if toks:
                ors = " OR ".join(f'"{t}"' for t in toks)
                rows = conn.execute("SELECT intents.* FROM intents_fts JOIN intents ON intents_fts.rowid = intents.id WHERE intents_fts MATCH ? ORDER BY rank LIMIT 2", (ors,)).fetchall()
                intents = [dict(r) for r in rows]
        except Exception:
            pass
        # 2. session summary level
        sess_hits = []
        try:
            toks = [t for t in query.lower().split() if len(t) >= 3][:6]
            if toks:
                ors = " OR ".join(f'"{t}"' for t in toks)
                rows = conn.execute("SELECT session_id, summary FROM session_summaries_fts WHERE session_summaries_fts MATCH ? ORDER BY rank LIMIT ?", (ors, k)).fetchall()
                sess_hits = [dict(r) for r in rows]
        except Exception:
            pass
        # 3. atomic claims level (H1.1 staged, self-contained)
        atomic_hits = []
        try:
            toks = [t for t in query.lower().split() if len(t) >= 3][:6]
            if toks:
                ors = " OR ".join(f'"{t}"' for t in toks)
                rows = conn.execute("SELECT claim_text, session_id, subject, object FROM atomic_claims_fts WHERE atomic_claims_fts MATCH ? ORDER BY rank LIMIT ?", (ors, k)).fetchall()
                atomic_hits = [dict(r) for r in rows]
        except Exception:
            pass
        conn.close()
        # 4. chunk level via normal recall
        chunks = self.recall(query, k=k)
        # annotate levels for explainability
        results = []
        for it in intents:
            results.append({"hcil_level": "intent", "summary": it["summary"], "id": it["id"], "correction": it.get("correction","")})
        for sh in sess_hits:
            results.append({"hcil_level": "session", "session_id": sh["session_id"], "summary": sh["summary"]})
        for ah in atomic_hits:
            results.append({"hcil_level": "atomic", "claim_text": ah["claim_text"], "session_id": ah["session_id"], "subject": ah["subject"]})
        for ch in chunks:
            ch["hcil_level"] = "chunk"
            results.append(ch)
        return results[:k+3]

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