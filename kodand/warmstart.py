"""
kodand.warmstart - Warm start for C2 (Session Start Context Injection)
Automatically injects active decisions, recent corrections, and open intents
at session start so the agent never starts cold.
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from kodand.store import get_store


class WarmStart:
    """Warm start context provider - injects relevant memory at session start."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)

    def get_warm_context(self, max_entries: int = 10) -> str:
        """Get warm start context string for session start."""
        entries = self.store.list_memories(scope="repo", state="active")
        if not entries:
            return ""

        # Group by type
        decisions = []
        corrections = []
        others = []

        for e in entries:
            t = e.get("memory_type", e.get("type", "reference"))
            if t == "decision":
                decisions.append(e)
            elif t == "correction":
                corrections.append(e)
            else:
                others.append(e)

        lines = []
        lines.append("# Kodand Warm Start Context")
        lines.append("")

        if decisions:
            lines.append("## Active Decisions")
            for d in decisions[:5]:
                lines.append(f"- {d.get('content', '')[:120]}")
            lines.append("")

        if corrections:
            lines.append("## Recent Corrections")
            for c in corrections[:5]:
                lines.append(f"- {c.get('content', '')[:120]}")
            lines.append("")

        if others:
            lines.append("## Recent Context")
            for o in others[:5]:
                lines.append(f"- {o.get('content', '')[:120]}")
            lines.append("")

        return "\n".join(lines)

    def get_context_json(self) -> dict:
        """Get warm context as JSON for programmatic use."""
        entries = self.store.list_memories(scope="repo", state="active")
        return {
            "repo_path": self.repo_path,
            "entry_count": len(entries),
            "entries": entries[:10],
            "generated_at": datetime.now().isoformat(),
        }


def create_warm_start(repo_path: str = None) -> WarmStart:
    """Create a warm start instance."""
    return WarmStart(repo_path)


def get_warm_context(repo_path: str = None) -> str:
    """Quick warm context string."""
    ws = WarmStart(repo_path)
    return ws.get_warm_context()