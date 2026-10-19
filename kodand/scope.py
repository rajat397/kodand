"""
kodand.scope - Cross-repo/org scope management (C9.3)
Org/team/repo/session inheritance with privacy boundaries.
Scope hierarchy: org > team > repo > session
Entries flow DOWNWARD (org → team → repo → session), never upward without promotion.
"""

from typing import List, Dict, Any, Optional
from kodand.store import get_store


class ScopeManager:
    """Scope hierarchy management with privacy boundaries."""

    SCOPE_ORDER = {"personal": 0, "session": 1, "repo": 2, "team": 3, "org": 4}

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)
        self._scope_cache: Dict[str, str] = {}

    import os

    def scope_of(self, entity_id: str, entity_type: str = "repo") -> str:
        """Get the scope of an entity."""
        key = f"{entity_type}:{entity_id}"
        if key in self._scope_cache:
            return self._scope_cache[key]
        # Default to repo scope
        self._scope_cache[key] = "repo"
        return "repo"

    def can_see(self, viewer_scope: str, viewer_name: str, entry_scope: str, entry_owner: str) -> bool:
        """Check if viewer can see an entry based on scope visibility rules.
        
        Rules:
        - An entry is visible to its own scope and all narrower (more specific) scopes
        - A repo-scoped entry is visible within that repo
        - A team-scoped entry is visible to all repos in that team
        - An org-scoped entry is visible to all teams/repos in that org
        - Personal entries are only visible to their owner
        """
        viewer_level = self.SCOPE_ORDER.get(viewer_scope, 0)
        entry_level = self.SCOPE_ORDER.get(entry_scope, 2)

        # A viewer can see entries at the same level or broader (lower number)
        # Personal entries are only visible to their owner
        if entry_scope == "personal":
            return viewer_name == entry_owner

        return viewer_level >= entry_level

    def filter_entries(self, entries: List[Dict], viewer_scope: str, viewer_name: str) -> List[Dict]:
        """Filter entries based on scope visibility."""
        return [e for e in entries if self.can_viewer_see_entry(viewer_scope, viewer_name, e)]

    def can_viewer_see_entry(self, viewer_scope: str, viewer_name: str, entry: Dict) -> bool:
        entry_scope = entry.get("scope", "repo")
        entry_owner = entry.get("scope", "repo")  # owner defaults to scope name
        return self.can_access(viewer_scope, viewer_name, entry_scope, entry_owner)

    def can_access(self, viewer_scope: str, viewer_name: str, entry_scope: str, entry_owner: str) -> bool:
        """Check if viewer can access an entry."""
        viewer_level = self.SCOPE_ORDER.get(viewer_scope, 2)
        entry_level = self.SCOPE_ORDER.get(entry_scope, 2)

        if entry_scope == "personal":
            return viewer_name == entry_owner

        return viewer_level >= entry_level


def create_scope_manager(repo_path: str = None) -> ScopeManager:
    """Create a scope manager instance."""
    return ScopeManager(repo_path)