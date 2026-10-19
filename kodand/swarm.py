"""
kodand.swarm - Team & Swarm coordination (C4)
Parallel agents coordinate with atomic SQLite claims: one winner per resource,
cross-process safe via UNIQUE(resource) + BEGIN IMMEDIATE. deny-and-propose
on conflict. No in-memory dict as source of truth.
"""

import os
import sqlite3
import time
import uuid
from typing import Dict, Any, List

from kodand.store import get_store


def _claims_conn(repo_path: str) -> sqlite3.Connection:
    # Ensure DB + schema exist via the store, then open a dedicated connection
    # with row access and a busy timeout for contended claims.
    store = get_store(repo_path)
    conn = sqlite3.connect(store.db_path, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=5000")
    except Exception:
        pass
    return conn


class SwarmCoordination:
    """Team coordination layer - atomic claims, deny-and-propose, shared state."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(self.repo_path)

    def claim(self, resource: str, session_id: str, ttl: int = 300) -> Dict[str, Any]:
        """Atomically claim a resource. Exactly one winner cross-process."""
        now = time.time()
        expires = now + ttl
        claim_id = str(uuid.uuid4())
        conn = _claims_conn(self.repo_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            # Reap expired claims inside the same write transaction.
            conn.execute("DELETE FROM claims WHERE expires_at <= ?", (now,))
            try:
                conn.execute(
                    "INSERT INTO claims (resource, session_id, claim_id, claimed_at, expires_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (resource, session_id, claim_id, now, expires),
                )
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT session_id, claim_id, claimed_at, expires_at FROM claims WHERE resource = ?",
                    (resource,),
                ).fetchone()
                conn.execute("ROLLBACK")
                holder = dict(row) if row else {}
                return {
                    "allowed": False,
                    "reason": f"Already claimed by session {holder.get('session_id', '?')}",
                    "existing_claim": {
                        "id": holder.get("claim_id"),
                        "session_id": holder.get("session_id"),
                        "claimed_at": holder.get("claimed_at"),
                        "expires_at": holder.get("expires_at"),
                    },
                    "action": "deny-and-propose",
                }
            conn.execute("COMMIT")
        except sqlite3.OperationalError as e:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            return {"allowed": False, "reason": f"claim contention: {e}", "action": "retry"}
        finally:
            conn.close()

        # Persist to store (after commit; claim record is in claims table).
        try:
            self.store.remember(
                content=f"Claim: {resource} by {session_id}",
                surface="text",
                locator=f"claim:{resource}",
                scope="repo",
                session_id=session_id,
            )
        except Exception:
            pass
        return {
            "allowed": True,
            "claim_id": claim_id,
            "resource": resource,
            "session_id": session_id,
            "claimed_at": now,
            "expires_at": expires,
        }

    def release(self, resource: str, session_id: str) -> bool:
        """Release a claim held by this session."""
        conn = _claims_conn(self.repo_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                "DELETE FROM claims WHERE resource = ? AND session_id = ?",
                (resource, session_id),
            )
            conn.execute("COMMIT")
            return cur.rowcount > 0
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            return False
        finally:
            conn.close()

    def check_access(self, resource: str, session_id: str) -> Dict[str, Any]:
        """Check if a session can access a resource."""
        conn = _claims_conn(self.repo_path)
        try:
            row = conn.execute(
                "SELECT session_id, expires_at FROM claims WHERE resource = ?",
                (resource,),
            ).fetchone()
        finally:
            conn.close()
        now = time.time()
        if not row:
            return {"allowed": True, "reason": "No active claim"}
        if row["session_id"] == session_id:
            return {"allowed": True, "reason": "Owned by this session"}
        if (row["expires_at"] or 0) <= now:
            self.release(resource, row["session_id"])
            return {"allowed": True, "reason": "Claim expired"}
        return {
            "allowed": False,
            "reason": f"Claimed by session {row['session_id']}",
            "holds": row["session_id"],
            "expires_at": row["expires_at"],
        }

    def get_active_claims(self) -> List[Dict[str, Any]]:
        """Get all active claims."""
        conn = _claims_conn(self.repo_path)
        try:
            rows = conn.execute(
                "SELECT resource, session_id, claim_id, claimed_at, expires_at "
                "FROM claims WHERE expires_at > ?",
                (time.time(),),
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "rule_id": r["claim_id"],
                "resource": r["resource"],
                "session_id": r["session_id"],
                "claimed_at": r["claimed_at"],
                "expires_at": r["expires_at"],
            }
            for r in rows
        ]

    def cleanup_expired(self) -> int:
        """Remove expired claims and return count removed."""
        conn = _claims_conn(self.repo_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute("DELETE FROM claims WHERE expires_at <= ?", (time.time(),))
            conn.execute("COMMIT")
            return cur.rowcount
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            return 0
        finally:
            conn.close()


def create_swarm_coordination(repo_path: str = None) -> SwarmCoordination:
    """Create a swarm coordination instance."""
    return SwarmCoordination(repo_path)
