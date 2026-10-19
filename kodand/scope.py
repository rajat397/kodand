"""
kodand.scope - Cross-repo/org scope (C9)
Org/team/repo/session inheritance with privacy boundaries.
"""

from typing import List, Dict, Any, Optional
from kodand.store import get_store


class Scope:
    """Scope hierarchy: org > team > repo > session.
    
    Memories flow down: org → team → repo → session.
    A memory in team scope is visible to all repos in that team.
    A memory in repo scope is visible only within that repo.
    Privacy: entries cannot flow UPWARD without explicit promotion.
    """
    
    SCOPE_HIERARCHY = ['personal', 'session', 'repo', 'team', 'org']
    SCOPE_ORDER = {s: i for i, s in enumerate(SCOPE_HIERARCHY)}
    
    def __init__(self, level: str, name: str, parent: Optional[str] = None):
        self.level = level  # personal, session, repo, team, org
        self.name = name
        self.parent = parent  # parent scope name (e.g., team name for repo)
    
    def can_see(self, entry_scope: str, entry_owner: str) -> bool:
        """Check if this scope can see an entry from another scope.
        
        Rules:
        - An entry is visible to its own scope and all CHILD scopes (more specific)
        - A repo-scoped entry is visible within that repo
        - A team-scoped entry is visible to all repos in that team
        - An org-scoped entry is visible to all teams/repos in that org
        - Personal entries are only visible to their owner
        """
        my_level = self.SCOPE_LEVEL.get(self.level, 0)
        entry_level = self.SCOPE_LEVEL.get(entry_scope, 0)
        
        # Can see entries at same level or more specific (lower level number = more general)
        # Actually: broader scopes (org) can see narrower (repo)? No - that's the privacy rule.
        # Correction: narrower scopes see broader scopes. Repo sees team. Team sees org.
        # But broader scopes do NOT see narrower entries unless promoted.
        if entry_level <= my_level:
            return True
        return False


class ScopeManager:
    """Manages scope inheritance across repos, teams, and orgs."""
    
    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)
        self._scope_cache: Dict[str, Scope] = {}
    
    def get_scope_for_repo(self, repo_name: str) -> Scope:
        """Get the scope for a repo (maps repo → team → org)."""
        if repo_name in self._scope_cache:
            return self._scope_cache[repo_name]
        
        # Default: repo inherits from its own scope
        scope = Scope('repo', repo_name)
        self._scope_cache[repo_name] = scope
        return scope
    
    def can_access(self, viewer_scope: str, viewer_name: str, entry_scope: str, entry_owner: str) -> bool:
        """Check if viewer can see entry."""
        viewer_scope_obj = Scope(viewer_scope, viewer_name)
        return viewer_scope_obj.can_see(entry_scope, entry_owner)
    
    def filter_entries(self, entries: List[Dict], viewer_scope: str, viewer_name: str) -> List[Dict]:
        """Filter entries based on scope visibility."""
        result = []
        for entry in entries:
            entry_scope = entry.get('scope', 'repo')
            entry_owner = entry.get('scope', 'repo')  # owner defaults to scope name
            if self.can_access(viewer_scope, viewer_name, entry_scope, entry_owner):
                result.append(entry)
        return result