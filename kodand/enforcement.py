"""
kodand.enforcement - Enforcement ladder (C7.4)
Promote high-utility memories from context text → hooks → repo lint/test/CI
checks that travel with git.
"""

import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from kodand.store import get_store


class EnforcementLadder:
    """Enforcement ladder: promote memories from context → hooks → repo checks.
    
    Ladder levels:
    1. CONTEXT - Memory in context window only
    2. HOOK - Enforced by tool hook
    3. LINT - Enforced by repo lint config
    4. TEST - Enforced by test
    5. CI - Enforced by CI check (travels with git)
    """

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)

    def promote(self, entry_id: int, level: str) -> bool:
        """Promote a memory entry to a higher enforcement level."""
        valid_levels = ["context", "hook", "lint", "test", "ci"]
        if level not in valid_levels:
            return False

        conn = self.store._get_conn()
        # Ensure enforcement_level column exists (migration)
        try:
            conn.execute("ALTER TABLE memories ADD COLUMN enforcement_level TEXT DEFAULT 'context'")
            conn.commit()
        except Exception:
            pass
        row = conn.execute(
            "SELECT * FROM memories WHERE id = ?", (entry_id,)
        ).fetchone()
        if not row:
            conn.close()
            return False

        # Update the memory entry with enforcement level
        conn.execute(
            "UPDATE memories SET enforcement_level = ? WHERE id = ?",
            (level, entry_id)
        )
        conn.commit()
        conn.close()

        # Log the promotion
        self.store.log_event(
            kind="promotion",
            entry_id=entry_id,
            provenance="enforcement.cli",
            detail=json.dumps({
                "entry_id": entry_id,
                "promoted_to": level,
            }),
        )

        return True

    def get_enforcement_level(self, entry_id: int) -> str:
        """Get the current enforcement level for an entry."""
        conn = self.store._get_conn()
        row = conn.execute(
            "SELECT enforcement_level FROM memories WHERE id = ?",
            (entry_id,)
        ).fetchone()
        conn.close()
        if row:
            return row["enforcement_level"] or "context"
        return "context"

    def get_entries_at_level(self, level: str) -> List[Dict]:
        """Get all entries at a given enforcement level."""
        conn = self.store._get_conn()
        rows = conn.execute(
            "SELECT * FROM memories WHERE enforcement_level = ? AND state = 'active'",
            (level,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_enforcement_summary(self) -> Dict[str, int]:
        """Get count of entries at each enforcement level."""
        levels = ["context", "hook", "lint", "test", "ci"]
        result = {}
        conn = self.store._get_conn()
        for level in levels:
            count = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE enforcement_level = ? AND state = 'active'",
                (level,)
            ).fetchone()[0]
            result[level] = count
        conn.close()
        return result


def create_enforcement_ladder(repo_path: str = None) -> EnforcementLadder:
    """Create an enforcement ladder instance."""
    return EnforcementLadder(repo_path)