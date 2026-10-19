"""
kodand.scope - Scopes with inheritance (Tranche 2.4, C9)
Personal / repo / session with provenance. Secret/PII exclusion at write time.
"""
import re, os, json
from kodand.store import get_store

SECRET_PAT = re.compile(r"(sk-|ghp_|api[_-]?key|password|secret)", re.I)
PII_PAT = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

def _is_secret(content: str) -> bool:
    return bool(SECRET_PAT.search(content))

def _has_pii(content: str) -> bool:
    return bool(PII_PAT.search(content))

def check_write(content: str):
    if _is_secret(content):
        return False, "secret detected — excluded at write time"
    if _has_pii(content):
        return False, "PII detected — excluded at write time"
    return True, ""

def can_see(entry_scope: str, viewer_scope: str) -> bool:
    order = {"personal":0, "session":1, "repo":2, "team":3, "org":4}
    return order.get(viewer_scope,2) >= order.get(entry_scope,2)

def filter_by_scope(entries, viewer_scope="repo"):
    return [e for e in entries if can_see(e.get("scope","repo"), viewer_scope)]
