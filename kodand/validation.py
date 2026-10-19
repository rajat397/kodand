"""
kodand.validation - Lazy validation + content-hash anchors (Tranche 2.3, Fix 2)
Anchors bind an entry to file/symbol content (sha256 of normalized source),
not just file existence. Re-resolve by symbol on read: body rewrite -> stale;
symbol moved / whitespace-only edit -> fresh.
"""
import ast
import hashlib
import os
import subprocess
import time
from kodand.store import get_store


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n"))


def _hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


def _git_head(repo_path: str) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_path,
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _resolve_symbol(repo_path: str, file_path: str, symbol: str):
    """Return (source_text, start, end, confidence) for symbol in file.

    confidence 'high' when resolved via AST; 'low' for whole-file fallback.
    Returns (None, 0, 0, 'missing') when the file/symbol cannot be resolved.
    """
    full = os.path.join(repo_path, file_path) if not os.path.isabs(file_path) else file_path
    if not os.path.exists(full):
        return None, 0, 0, "missing"
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return None, 0, 0, "missing"
    if not symbol:
        return text, 1, len(text.splitlines()), "low"
    name = symbol.split(".")[-1].split(":")[0].strip()
    if not name:
        return text, 1, len(text.splitlines()), "low"
    try:
        tree = ast.parse(text)
    except Exception:
        return text, 1, len(text.splitlines()), "low"
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            try:
                seg = ast.get_source_segment(text, node)
            except Exception:
                seg = None
            if seg is None:
                lines = text.splitlines()
                s = getattr(node, "lineno", 1)
                e = getattr(node, "end_lineno", s)
                seg = "\n".join(lines[s - 1:e])
            return seg, getattr(node, "lineno", 0), getattr(node, "end_lineno", 0), "high"
    return None, 0, 0, "missing"


def anchor_entry(repo_path: str, entry_id: int, locator: str) -> bool:
    """Create/update the content-hash anchor for an entry. Best-effort, never raises."""
    try:
        if not locator or ("/" not in locator and "." not in locator and ":" not in locator):
            return False
        parts = locator.split(":")
        file_part = parts[0]
        symbol = parts[1] if len(parts) > 1 else ""
        if "/" not in file_part and "." not in file_part:
            return False  # not a file locator (e.g. claim:..., session markers)
        src, start, end, conf = _resolve_symbol(repo_path, file_part, symbol)
        if src is None:
            return False
        store = get_store(repo_path)
        conn = store._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO anchors "
                "(entry_id, file_path, symbol, start_line, end_line, content_hash, commit_hash, confidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (entry_id, file_part, symbol, start, end, _hash(src), _git_head(repo_path), conf),
            )
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception:
        return False


def is_stale(entry: dict, repo_path: str) -> bool:
    """Check if entry's evidence is stale via content-hash anchor, else legacy existence check."""
    loc = entry.get("locator", "")
    repo_path = repo_path or os.getcwd()
    # Anchor path: compare current content hash with stored hash.
    try:
        store = get_store(repo_path)
        conn = store._get_conn()
        try:
            row = conn.execute(
                "SELECT file_path, symbol, content_hash, confidence FROM anchors WHERE entry_id = ?",
                (entry.get("id"),),
            ).fetchone()
        finally:
            conn.close()
        if row:
            anchor = dict(row)
            src, _, _, conf = _resolve_symbol(repo_path, anchor["file_path"], anchor.get("symbol", ""))
            if src is None:
                return True  # file or symbol gone
            if conf == "missing":
                return True
            return _hash(src) != anchor["content_hash"]
    except Exception:
        pass
    # Legacy fallback: file-missing only.
    if not loc or ":" not in loc:
        return False
    file_part = loc.split(":")[0]
    full = os.path.join(repo_path, file_part)
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
        msg = f"Stale evidence for #{entry_id}: {entry.get('locator','')} changed or not found"
        # warn-only, never block without recourse
        store.log_event("held", entry_id, "validation.lazy", msg)
        return True, f"WARN: {msg} — proceeding with warning"
    store.log_event("validated", entry_id, "validation.lazy", "evidence ok")
    return True, ""
