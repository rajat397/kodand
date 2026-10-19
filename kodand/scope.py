"""
kodand.scope - Scopes with inheritance (Tranche 2.4, C9)
Personal / repo / session with provenance. Secret/PII exclusion at write time.

Fix 6: shape-based detection. Blocks key SHAPES (provider prefixes, PEM
blocks, credential assignments with values, high-entropy bearer tokens),
not bare words. "password retry policy" and prose emails are allowed.
"""
import math
import re
from kodand.store import get_store

# Provider-prefixed key shapes (high precision, no context needed).
KEY_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "aws-access-key"),
    (r"gh[pousr]_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,}", "github-token"),
    (r"xox[bap]-[A-Za-z0-9\-]{8,}", "slack-token"),
    (r"sk-(live|test)-[A-Za-z0-9]{8,}|sk-[A-Za-z0-9]{20,}", "api-key-sk"),
    (r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", "pem-private-key"),
    (r"(?i)bearer\s+[A-Za-z0-9_\-\.~]{20,}", "bearer-token"),
]
KEY_RES = [(re.compile(p), name) for p, name in KEY_PATTERNS]

# Credential ASSIGNMENTS (word + value shape). Bare words never match.
ASSIGN_RES = [
    (re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?"), "api-key-assignment"),
    (re.compile(r"(?i)password\s*[:=]\s*['\"]?(\S{4,})['\"]?"), "password-assignment"),
    (re.compile(r"(?i)secret\s*[:=]\s*['\"]([^'\"]{8,})['\"]"), "secret-assignment"),
]

PLACEHOLDER_WORDS = {"password", "secret", "changeme", "example", "xxx", "***", "redacted", "null", "none"}

PII_PAT = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    from collections import Counter
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _has_high_entropy_token(content: str) -> str | None:
    for m in re.finditer(r"\b[A-Za-z0-9_\-]{32,}\b", content):
        tok = m.group(0)
        if _entropy(tok) >= 4.5:
            return tok
    return None


def _is_secret(content: str):
    for rx, name in KEY_RES:
        if rx.search(content):
            return True, name
    for rx, name in ASSIGN_RES:
        m = rx.search(content)
        if m:
            # Reject placeholder values ("password = secret", "xxx").
            val = ""
            try:
                val = (m.group(1) or "").strip("'\"").lower()
            except Exception:
                val = ""
            if val and val not in PLACEHOLDER_WORDS and not set(val) <= set("*x"):
                return True, name
    tok = _has_high_entropy_token(content)
    if tok:
        return True, "high-entropy-token"
    return False, ""


def _has_pii(content: str) -> bool:
    return bool(PII_PAT.search(content))


def check_write(content: str):
    hit, kind = _is_secret(content)
    if hit:
        return False, f"secret detected ({kind}) — excluded at write time"
    # Email alone in prose is allowed; it only matters paired with a secret,
    # which is already blocked above. Never block on email by itself.
    return True, ""


def can_see(entry_scope: str, viewer_scope: str) -> bool:
    order = {"personal": 0, "session": 1, "repo": 2, "team": 3, "org": 4}
    return order.get(viewer_scope, 2) >= order.get(entry_scope, 2)


def filter_by_scope(entries, viewer_scope="repo"):
    return [e for e in entries if can_see(e.get("scope", "repo"), viewer_scope)]
