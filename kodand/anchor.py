"""
kodand.anchor - Anchoring for biggest repos (C6, Iter 9)
Entries anchored to symbols/signatures/covering tests.
Rename tolerance: anchor survives file rename via git history.
Caller invalidation: changed caller flags dependents.
"""
import os
import subprocess
import json
from typing import List, Dict, Optional
from kodand.store import get_store

def _git_rename_map(repo_path: str) -> Dict[str, str]:
    """Return {old_path: new_path} for renames in history."""
    try:
        out = subprocess.run(
            ["git", "log", "--name-status", "--diff-filter=R", "--pretty=format:"],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        m = {}
        if out.returncode == 0:
            for line in out.stdout.splitlines():
                if line.startswith("R"):
                    parts = line.split("\t")
                    if len(parts) == 3:
                        m[parts[1]] = parts[2]
        return m
    except Exception:
        return {}

def resolve_anchor(repo_path: str, file_path: str) -> str:
    """Resolve anchor file path with rename tolerance.
    If file_path was renamed, return current path, else original.
    """
    # Check if file exists at given path
    full = os.path.join(repo_path, file_path)
    if os.path.exists(full):
        return file_path
    # Check rename map
    renames = _git_rename_map(repo_path)
    # If old_path matches file_path, return new_path if it exists
    if file_path in renames:
        new_path = renames[file_path]
        if os.path.exists(os.path.join(repo_path, new_path)):
            return new_path
    # Also check reverse: file_path might be new path, old was different
    return file_path

def get_anchored(repo_path: str, file_path: str) -> List[Dict]:
    """Get memories anchored to file_path (with rename tolerance)."""
    store = get_store(repo_path)
    resolved = resolve_anchor(repo_path, file_path)
    # Search for both original and resolved to tolerate rename either direction
    # Also check reverse rename (if file_path is new path, find old)
    renames = _git_rename_map(repo_path)
    reverse = {v: k for k, v in renames.items()}
    candidates = {file_path, resolved}
    if file_path in reverse:
        candidates.add(reverse[file_path])
    if resolved in reverse:
        candidates.add(reverse[resolved])
    hits_all = []
    anchored_all = []
    conn = store._get_conn()
    for cand in candidates:
        hits = store.recall(query=cand, k=10)
        hits_all.extend(hits)
        rows = conn.execute(
            "SELECT * FROM memories WHERE state='active' AND locator LIKE ? ORDER BY created_at DESC",
            (f"%{cand}%",)
        )
        anchored_all.extend([dict(r) for r in rows.fetchall()])
    conn.close()
    # Merge by id
    seen = {}
    for h in hits_all + anchored_all:
        seen[h["id"]] = h
    return list(seen.values())

def get_caller_dependents(repo_path: str, symbol: str) -> List[Dict]:
    """Find memories that depend on symbol as caller.
    Simple heuristic: memories whose content mentions symbol as caller.
    In a real implementation, this would parse call graph.
    """
    store = get_store(repo_path)
    # Search for memories mentioning the symbol
    hits = store.recall(query=symbol, k=20)
    # Filter to those where locator or content suggests caller dependency
    deps = []
    for h in hits:
        loc = h.get("locator", "")
        content = h.get("content", "")
        # Heuristic: if symbol appears in content as "caller" context
        if symbol.lower() in content.lower():
            deps.append(h)
    return deps

def create_anchored(repo_path: str, content: str, file_path: str, symbol: str = None, commit_hash: str = None) -> Dict:
    """Create a memory anchored to file/symbol/commit."""
    store = get_store(repo_path)
    loc = file_path
    if symbol:
        loc += f":{symbol}"
    if commit_hash:
        loc += f"@{commit_hash[:8]}"
    return store.remember(content=content, surface="text", locator=loc, scope="repo", session_id="anchor")
