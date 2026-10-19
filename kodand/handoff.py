"""
kodand.handoff - Session handoff (C4.4)
Capture a session's intent ledger (decided/done/blocked) so any fresh session
resumes without human re-briefing.
"""

import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from kodand.store import get_store


class Handoff:
    """Session handoff record - captures intent ledger for resumption."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)

    def capture(self, session_id: str, decided: List[str] = None,
                done: List[str] = None, blocked: List[str] = None,
                context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Capture a session's intent ledger for handoff."""
        handoff_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        handoff_entry = {
            "id": handoff_id,
            "repo_path": self.repo_path,
            "session_id": session_id,
            "decided": decided or [],
            "done": done or [],
            "blocked": blocked or [],
            "context": context or {},
            "created_at": timestamp,
            "type": "handoff",
        }

        # Store as memory entry
        self.store.remember(
            content=f"Session handoff: {len(decided or [])} decided, {len(done or [])} done, {len(blocked or [])} blocked",
            surface="text",
            locator=f"handoff:{session_id}",
            scope="repo",
            session_id=session_id,
        )

        # Log event
        self.store.log_event(
            kind="handoff",
            entry_id=None,
            provenance="handoff.cli",
            detail=json.dumps({
                "handoff_id": handoff_id,
                "session_id": session_id,
                "decided_count": len(decided or []),
                "done_count": len(done or []),
                "blocked_count": len(blocked or []),
            }),
        )

        return {
            "handoff_id": handoff_id,
            "session_id": session_id,
            "decided": decided or [],
            "done": done or [],
            "blocked": blocked or [],
            "context": context or {},
            "created_at": timestamp,
        }

    def resume(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent handoff for a session to resume work."""
        conn = self.store._get_conn()
        row = conn.execute(
            "SELECT * FROM memories WHERE surface='text' AND locator LIKE ? AND session_id=? ORDER BY created_at DESC LIMIT 1",
            (f"handoff:{session_id}%", session_id)
        ).fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_all_handsoffs(self, repo_path: str = None) -> List[Dict[str, Any]]:
        """Get all handoff entries for a repo."""
        store = get_store(repo_path or self.repo_path)
        entries = store.list_memories(scope="repo")
        return [e for e in entries if e.get("type") == "handoff"]


def create_handoff(repo_path: str = None) -> Handoff:
    """Create a handoff instance."""
    return Handoff(repo_path)


def capture_session(repo_path: str, session_id: str,
                    decided: List[str] = None, done: List[str] = None,
                    blocked: List[str] = None,
                    context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Quick capture session function."""
    handoff = Handoff(repo_path)
    return handoff.capture(session_id, decided, done, blocked, context)


def resume_session(repo_path: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Quick resume session function."""
    handoff = Handoff(repo_path)
    return handoff.resume(session_id)