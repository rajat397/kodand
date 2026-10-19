"""
kodand.outcome - Outcome labeling (Tranche 2.1)
Marks each applied entry as avoided a mistake, caused one, or noise.
"""

from typing import Dict, Any, Optional
from kodand.store import get_store


class OutcomeLabeler:
    """Labels memory entries with outcome labels."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)

    def label_entry(self, entry_id: int, outcome: str, note: str = "", holdout: bool = False) -> bool:
        """Label a memory entry with an outcome label.
        
        Args:
            entry_id: ID of the memory entry
            outcome: One of 'avoided_mistake', 'caused_mistake', 'noise'
            note: Optional note about why this outcome was assigned
        
        Returns:
            True if successful, False if entry not found
        """
        import sqlite3
        conn = self.store._get_conn()
        # Ensure holdout column exists (migration for pre-existing DBs).
        try:
            conn.execute("ALTER TABLE memories ADD COLUMN is_holdout INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass

        # Check if entry exists
        row = conn.execute("SELECT id FROM memories WHERE id = ?", (entry_id,)).fetchone()
        if not row:
            conn.close()
            return False

        if holdout:
            # Counterfactual arm: flag the row so recall/ranking/utility exclude it.
            # The tag stays in the note for human readability only.
            conn.execute("UPDATE memories SET is_holdout = 1 WHERE id = ?", (entry_id,))
            note = (note + " [holdout]") if note else "[holdout]"
        
        # Log the outcome as an event
        conn.execute(
            "INSERT INTO events (ts, kind, entry_id, provenance, detail) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), "outcome_label", entry_id, "outcome_labeler",
             json.dumps({"outcome": outcome, "note": note}))
        )
        conn.commit()
        conn.close()
        return True

    def get_outcome_stats(self, repo_path: str = None) -> dict:
        """Get outcome statistics for a repo."""
        import sqlite3
        repo_path = repo_path or self.repo_path
        store = get_store(repo_path)
        conn = store._get_conn()
        
        total = conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'outcome_label'"
        ).fetchone()[0]
        
        by_outcome = {}
        for outcome in ['avoided_mistake', 'caused_mistake', 'noise']:
            count = conn.execute(
                "SELECT COUNT(*) FROM events WHERE kind = 'outcome_label' AND detail LIKE ?",
                (f'%"{outcome}"%',)
            ).fetchone()[0]
            by_outcome[outcome] = count
        
        conn.close()
        return {
            "total": total,
            "by_outcome": by_outcome
        }


def create_outcome_labeler(repo_path: str = None) -> OutcomeLabeler:
    """Create an outcome labeler instance."""
    return OutcomeLabeler(repo_path)


import os
import json
from datetime import datetime