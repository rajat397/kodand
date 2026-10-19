"""
kodand.harness_adapter - Second-harness adapter (C9.1)
Same store, second harness, same warm start and recall.

Enables kodand to run on multiple harnesses simultaneously, sharing the
same store but adapting to each harness's hook surface.
"""

from typing import Dict, Any, Optional, Callable
from kodand.store import get_store
from kodand.recall import create_recall_engine
from kodand.warmstart import create_warm_start
from kodand.trust import TrustSurface


class HarnessAdapter:
    """Base adapter for a specific harness (opencode, claude-code, cursor, etc.).
    
    Provides a common interface for:
    - Warm start injection at session start
    - Prospective recall on tool calls
    - Trust surface access
    - Capture of events
    """
    
    def __init__(self, repo_path: str = None, harness_name: str = 'generic'):
        self.repo_path = repo_path or os.getcwd()
        self.harness_name = harness_name
        self.store = get_store(self.repo_path)
        self.warmstart = create_warm_start(self.repo_path)
        self.recall_engine = create_recall_engine(self.repo_path)
        self.trust = TrustSurface(self.repo_path)
        self._capture_enabled = True
    
    def get_warm_context(self) -> str:
        """Get warm start context for session start."""
        return self.warmstart.get_warm_context()
    
    def get_prospective_recall(self, context: Dict[str, Any]) -> List[Dict]:
        """Get prospective recall entries for a tool call context."""
        return self.recall_engine.prospective_recall(context)
    
    def trust_list(self, scope: str = None) -> List[Dict]:
        """List trust surface entries."""
        return self.trust.list(scope=scope)
    
    def trust_inspect(self, entry_id: int) -> Optional[Dict]:
        """Inspect a specific memory entry."""
        return self.trust.inspect(entry_id)
    
    def trust_correct(self, entry_id: int, kind: str, note: str) -> bool:
        """Correct a memory entry."""
        return self.trust.correct(entry_id, kind, note)
    
    def trust_delete(self, entry_id: int) -> bool:
        """Delete/retire a memory entry."""
        return self.trust.delete(entry_id)
    
    def capture(self, content: str, surface: str = 'text', locator: str = '',
                scope: str = 'repo', session_id: str = None) -> dict:
        """Capture a memory event from the harness."""
        return self.store.remember(
            content=content,
            surface=surface,
            locator=locator,
            scope=scope,
            session_id=session_id,
        )
    
    def log_event(self, kind: str, entry_id: int = None, provenance: str = None,
                  detail: str = None):
        """Log an event to the event log."""
        self.store.log_event(kind, entry_id, provenance, detail)


import os


def create_adapter(repo_path: str = None, harness_name: str = 'generic') -> HarnessAdapter:
    """Create a harness adapter instance."""
    return HarnessAdapter(repo_path, harness_name)


# Registry of harness adapters
_ADAPTERS: Dict[str, HarnessAdapter] = {}


def get_adapter(repo_path: str, harness_name: str) -> HarnessAdapter:
    """Get or create a harness adapter for the given repo and harness."""
    key = f"{repo_path}:{harness_name}"
    if key not in _ADAPTERS:
        _ADAPTERS[key] = HarnessAdapter(repo_path, harness_name)
    return _ADAPTERS[key]