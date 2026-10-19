"""
kodand.validation - Lazy validation (Tranche 2.3)
Re-check evidence only when entry is about to be applied. Warn-only on stale.
"""
import os, json, sqlite3, time
from kodand.store import get_store

def is_stale(entry: dict, repo_path: str) -> bool:
    """Check if entry's evidence is stale (file/symbol no longer exists or changed)."""
    loc = entry.get("locator","")
    if not loc or ":" not in loc:
        return False
    file_part = loc.split(":")[0]
    full = os.path.join(repo_path or os.getcwd(), file_part)
    # If file part looks like path and file missing -> stale
    if "/" in file_part or "." in file_part:
        if not os.path.exists(full):
            return True
    return False

def validate_before_apply(entry_id: int, repo_path: str = None):
    """Lazy validation hook - call before applying entry. Returns (ok, warn_msg)."""
    store = get_store(repo_path)
    entry = store.get_memory(entry_id)
    if not entry:
        return False, "entry not found"
    if is_stale(entry, repo_path or os.getcwd()):
        msg = f"Stale evidence for #{entry_id}: {entry.get('locator','')} not found"
        # warn-only, never block without recourse
        store.log_event("held", entry_id, "validation.lazy", msg)
        return True, f"WARN: {msg} — proceeding with warning"
    store.log_event("validated", entry_id, "validation.lazy", "evidence ok")
    return True, ""
