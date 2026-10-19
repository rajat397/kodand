from typing import List, Dict, Any, Optional
"""
kodand.utility - Utility scoring (C2.2)
Utility scores drive retrieval rank, promotion, and decay.
"""

from typing import Dict, Any, Optional
from kodand.store import get_store


class UtilityScorer:
    """Utility scoring for memory entries."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)

    def compute_utility(self, entry_id: int) -> float:
        """Compute utility score for a memory entry.
        
        Utility = (helpful_count * 1.0) - (harmful_count * 1.0) + (usage_count * 0.1)
        """
        conn = self.store._get_conn()
        
        # Count positive outcomes
        positive = conn.execute(
            "SELECT COUNT(*) FROM events WHERE entry_id = ? AND kind = 'outcome_label' AND detail LIKE '%avoided_mistake%'",
            (entry_id,)
        ).fetchone()[0]
        
        # Count negative outcomes
        negative = conn.execute(
            "SELECT COUNT(*) FROM events WHERE entry_id = ? AND kind = 'outcome_label' AND detail LIKE '%caused_mistake%'",
            (entry_id,)
        ).fetchone()[0]
        
        # Count neutral outcomes
        neutral = conn.execute(
            "SELECT COUNT(*) FROM events WHERE entry_id = ? AND kind = 'outcome_label' AND detail LIKE '%noise%'",
            (entry_id,)
        ).fetchone()[0]
        
        # Count usage (recall events)
        usage = conn.execute(
            "SELECT COUNT(*) FROM events WHERE entry_id = ? AND kind = 'injected'",
            (entry_id,)
        ).fetchone()[0]
        
        conn.close()
        
        score = positive * 1.0 - negative * 1.0 + usage * 0.1
        return max(0.0, score)  # Utility can't be negative

    def get_top_entries(self, repo_path: str = None, limit: int = 10) -> List[Dict]:
        """Get top entries by utility score."""
        repo_path = repo_path or self.repo_path
        store = get_store(repo_path)
        entries = store.list_memories(scope="repo", state="active")
        
        # Score each entry
        scored = []
        for e in entries:
            score = self.compute_utility(e["id"])
            scored.append({**e, "utility": score})
        
        # Sort by utility descending
        scored.sort(key=lambda x: x["utility"], reverse=True)
        return scored[:limit]


def create_utility_scorer(repo_path: str = None) -> UtilityScorer:
    """Create a utility scorer instance."""
    return UtilityScorer(repo_path)


import os