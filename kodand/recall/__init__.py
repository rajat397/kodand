"""
kodand.recall - Prospective recall (C3)
Retrieves relevant memories based on context triggers.
"""

import os
from typing import List, Dict, Any, Optional
from kodand.store import get_store


class RecallEngine:
    """Prospective recall engine - matches context to stored memories."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)

    def recall(self, query: str = "", k: int = 5, scope: str = None) -> List[Dict]:
        """Retrieve relevant memories by keyword search. Ranked by utility when available."""
        hits = self.store.recall(query=query, k=k*3, scope=scope)
        # utility-driven ranking: if utility scorer has data, sort by utility
        try:
            from kodand.utility import UtilityScorer
            scorer = UtilityScorer(self.repo_path)
            for h in hits:
                h["_utility"] = scorer.compute_utility(h["id"])
            hits.sort(key=lambda x: (x["_utility"], x.get("created_at",0)), reverse=True)
            for h in hits:
                h.pop("_utility", None)
        except Exception:
            pass
        return hits[:k]

    def recall_by_file(self, file_path: str, k: int = 5) -> List[Dict]:
        """Recall memories anchored to a specific file."""
        conn = self.store._get_conn()
        rows = conn.execute(
            "SELECT * FROM memories WHERE state='active' AND locator LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{file_path}%", k)
        )
        entries = [dict(r) for r in rows.fetchall()]
        conn.close()
        return entries

    def recall_by_symbol(self, symbol: str, k: int = 5) -> List[Dict]:
        """Recall memories anchored to a specific symbol."""
        conn = self.store._get_conn()
        rows = conn.execute(
            "SELECT * FROM memories WHERE state='active' AND locator LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{symbol}%", k)
        )
        entries = [dict(r) for r in rows.fetchall()]
        conn.close()
        return entries

    def prospective_recall(self, context: Dict[str, Any]) -> List[Dict]:
        """Prospective recall - inject relevant memories based on context triggers.

        This is the key C3 mechanism: instead of waiting for the agent to ask,
        memories are proactively injected based on what the agent is about to do
        (file touched, command run, dependency added).
        """
        results = []

        # Check file_path
        if context.get("file_path"):
            results.extend(self.recall_by_file(context["file_path"], k=3))

        # Check symbol
        if context.get("symbol"):
            results.extend(self.recall_by_symbol(context["symbol"], k=3))

        # Check command
        if context.get("command"):
            results.extend(self.recall(query=context["command"], k=3))

        # Deduplicate by id
        seen = set()
        unique = []
        for r in results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)
        # utility ranking
        try:
            from kodand.utility import UtilityScorer
            scorer = UtilityScorer(self.repo_path)
            for h in unique:
                h["_utility"] = scorer.compute_utility(h["id"])
            unique.sort(key=lambda x: (x["_utility"], x.get("created_at",0)), reverse=True)
            for h in unique:
                h.pop("_utility", None)
        except Exception:
            pass
        return unique[:10]

    def get_anchored(self, entry_id: int) -> Optional[Dict]:
        """Get a specific anchored memory."""
        return self.store.get_memory(entry_id)


def create_recall_engine(repo_path: str = None) -> RecallEngine:
    """Create a recall engine instance."""
    return RecallEngine(repo_path)


def recall(query: str = "", k: int = 5, repo_path: str = None) -> List[Dict]:
    """Quick recall function."""
    engine = RecallEngine(repo_path)
    return engine.recall(query=query, k=k)


def prospective_recall(context: Dict[str, Any], repo_path: str = None) -> List[Dict]:
    """Quick prospective recall function."""
    engine = RecallEngine(repo_path)
    return engine.prospective_recall(context)