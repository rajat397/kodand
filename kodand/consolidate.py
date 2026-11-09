"""D5: consolidation worker (sleep-time batch, checkpointed, race-guarded).

Design (decisions #1/#5, spine-passed):
- only PROPOSES. The deterministic scan queues same-topic candidate pairs into
  merge_queue (status 'pending'); nothing mutates memory state. Human or surface
  resolves (CLI --resolve), which is where D2 authority takes over.
- batch is idempotent: a candidate id is UNIQUE in the queue; a re-run over the
  same rows re-enqueues nothing (added rows only).
- cursor: consolidation scans memories with id > last cursor (stored in the
  meta kv table); append-safe for new rows, no re-scan of settled work.
- race guard: flock(repo-lock) non-blocking; a second concurrent worker exits
  'busy' immediately (gate 4).
- laya-assist: reserved for the sleep-time model pass (env
  KODAND_CONSOLIDATE_LAYA=1); v1 is deterministic only because every model
  proposal needs the same audit trail anyway — the queue is the product.
"""

from __future__ import annotations

import fcntl
import json
import os
import time


def _lock_path(repo: str) -> str:
    return os.path.join(repo, ".kodand", "consolidate.lock")


class _SweptLock:
    def __init__(self, repo: str):
        os.makedirs(os.path.join(repo, ".kodand"), exist_ok=True)
        self.fh = open(_lock_path(repo), "w")  # noqa: SIM115 - lock guard, released in release()
        self.acquired = True
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.acquired = False

    def release(self) -> None:
        try:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
        finally:
            self.fh.close()


def _ensure_queue(store) -> None:
    conn = store._get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS merge_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        left_id INTEGER NOT NULL,
        right_id INTEGER NOT NULL,
        entity TEXT,
        reason TEXT,
        status TEXT DEFAULT 'pending',
        created_at REAL,
        decided_at REAL,
        decided_by TEXT,
        UNIQUE(left_id, right_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY, value TEXT)""")
    conn.commit()
    conn.close()


def _get_cursor(store) -> int:
    conn = store._get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key='consolidate_cursor'").fetchone()
    conn.close()
    return int(row["value"]) if row else 0


def _set_cursor(store, value: int) -> int:
    _ensure_queue(store)
    conn = store._get_conn()
    conn.execute("INSERT INTO meta(key, value) VALUES ('consolidate_cursor', ?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                 (str(value),))
    conn.commit()
    conn.close()
    return value


def propose(store, limit: int = 500) -> dict:
    """One deterministic batch: scan new rows, queue candidate pairs. Idempotent."""
    _ensure_queue(store)
    lock = _SweptLock(store.repo_path)
    if not lock.acquired:
        return {"status": "busy", "queued": 0}
    try:
        conn = store._get_conn()
        cursor = _get_cursor(store)
        rows = [dict(r) for r in conn.execute(
            "SELECT id, content, locator, memory_type, salience FROM memories "
            "WHERE id > ? AND state='active' ORDER BY id LIMIT ?",
            (cursor, limit)).fetchall()]
        queued = 0
        now = time.time()
        # Topics of the new rows, then EVERY active id in those bases (existing rows
        # included) so an incremental sweep pairs fresh rows with settled ones. The
        # UNIQUE(left_id, right_id) constraint keeps re-enqueues no-ops (idempotence).
        bases = set()
        for r in rows:
            item = (r.get("locator", "") or f"row-{r['id']}").split("#")[0]
            item = item.replace("artifact:", "").split("@")[0]
            bases.add(item)
        now = time.time()
        for base in sorted(bases):
            like = base.replace("%", "") + "%"
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM memories WHERE state='active' AND locator LIKE ? ORDER BY id",
                (like,)).fetchall()]
            if len(ids) < 2:
                continue
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    left, right = sorted((ids[i], ids[j]))
                    try:
                        conn.execute(
                            "INSERT INTO merge_queue (left_id, right_id, entity, reason, created_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (left, right, base, "same-topic candidate (deterministic scan)", now),
                        )
                        queued += 1
                    except Exception:  # noqa: BLE001, S110 - UNIQUE constraint => already queued (idempotence); log not needed
                        pass
        if rows:
            conn.execute("INSERT INTO meta(key, value) VALUES ('consolidate_cursor', ?) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                         (str(max(r["id"] for r in rows)),))
        newcursor = _get_cursor(store)
        conn.commit()
        conn.close()
        return {"status": "ok", "scanned": len(rows), "queued": queued,
                "cursor": newcursor}
    finally:
        lock.release()


def resolve(store, queue_id: int, decision: str, decided_by: str = "user") -> dict:
    """Apply a human decision to a queued candidate (D2: authority lives here)."""
    _ensure_queue(store)
    if decision not in ("merged", "rejected"):
        raise ValueError("decision must be 'merged' or 'rejected'")
    conn = store._get_conn()
    cur = conn.execute(
        "UPDATE merge_queue SET status=?, decided_at=?, decided_by=? "
        "WHERE id=? AND status='pending'",
        (decision, time.time(), decided_by, queue_id))
    committed = cur.rowcount
    conn.commit()
    conn.close()
    if committed:
        store.log_event("merge-resolved", entry_id=None, provenance=decided_by,
                        detail=json.dumps({"queue_id": queue_id, "decision": decision}))
    return {"resolved": bool(committed), "decision": decision}


def list_pending(store, limit: int = 50) -> list[dict]:
    _ensure_queue(store)
    conn = store._get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM merge_queue WHERE status='pending' ORDER BY id LIMIT ?",
        (limit,)).fetchall()]
    conn.close()
    return rows
