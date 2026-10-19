"""
kodand.store - SQLite-based memory storage
"""

import sqlite3
import os
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
        conn.close()

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
        conn = self._get_conn()
        if query:
            like = f"%{query}%"
            rows = conn.execute(
                "SELECT * FROM memories WHERE state='active' AND (content LIKE ? OR locator LIKE ?) "
                "ORDER BY created_at DESC LIMIT ?",
                (like, like, k)
            )
        else:
            rows = conn.execute(
                "SELECT * FROM memories WHERE state='active' ORDER BY created_at DESC LIMIT ?",
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