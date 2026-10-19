"""
kodand.trust - Trust surface (C8)
Inspect, correct, delete memories - the trust surface.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from kodand.store import get_store


class TrustSurface:
    """Trust surface for inspecting and correcting memories."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)

    def list(self, scope: str = None, freshness: str = "all") -> List[Dict]:
        """List all entries grouped by scope and freshness."""
        memories = self.store.list_memories(scope=scope)
        result = []
        for m in memories:
            result.append({
                "id": m["id"],
                "type": m.get("memory_type", "reference"),
                "content": m["content"][:100] + "..." if len(m.get("content", "")) > 100 else m.get("content", ""),
                "locator": m.get("locator", ""),
                "scope": m.get("scope", "repo"),
                "state": m.get("state", "active"),
                "created_at": m.get("created_at"),
                "updated_at": m.get("updated_at"),
            })
        return result

    def inspect(self, entry_id: int) -> Optional[Dict]:
        """Inspect a specific memory entry."""
        return self.store.get_memory(entry_id)

    def correct(self, entry_id: int, kind: str, note: str) -> bool:
        """Correct a wrong memory entry."""
        store = self.store
        entry = store.get_memory(entry_id)
        if not entry:
            return False

        # Log the correction
        store.log_event(
            kind="corrected",
            entry_id=entry_id,
            provenance="trust.cli",
            detail=json.dumps({"kind": kind, "note": note, "original": entry["content"]}),
        )

        # Update the entry with correction note
        conn = store._get_conn()
        now = datetime.now().timestamp()
        conn.execute(
            "UPDATE memories SET content = ?, updated_at = ? WHERE id = ?",
            (f"{entry['content']}\n\n[CORRECTION: {kind}] {note}", now, entry_id)
        )
        conn.commit()
        conn.close()
        return True

    def delete(self, entry_id: int) -> bool:
        """Soft-retire a memory entry."""
        return self.store.delete_memory(entry_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get trust surface statistics."""
        conn = self.store._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM memories WHERE state='active'").fetchone()[0]
        by_scope = {}
        for scope in ["personal", "repo", "session", "team"]:
            count = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE state='active' AND scope = ?",
                (scope,)
            ).fetchone()[0]
            by_scope[scope] = count
        conn.close()
        return {
            "total": total,
            "by_scope": by_scope,
        }


def create_trust_surface(repo_path: str = None) -> TrustSurface:
    """Create a trust surface instance."""
    return TrustSurface(repo_path)


def list_memories(repo_path: str = None, scope: str = None) -> List[Dict]:
    """Quick list function."""
    ts = TrustSurface(repo_path)
    return ts.list(scope=scope)


def inspect_entry(entry_id: int, repo_path: str = None) -> Optional[Dict]:
    """Quick inspect function."""
    ts = TrustSurface(repo_path)
    return ts.inspect(entry_id)


def correct_entry(entry_id: int, kind: str, note: str, repo_path: str = None) -> bool:
    """Quick correct function."""
    ts = TrustSurface(repo_path)
    return ts.correct(entry_id, kind, note)


def delete_entry(entry_id: int, repo_path: str = None) -> bool:
    """Quick delete function."""
    ts = TrustSurface(repo_path)
    return ts.delete(entry_id)