"""
kodand.capture.corrections - Deterministic correction classifier (Fix 5, v1).

Matches explicit user corrections in session transcripts. stdlib only,
no ML classifier until this baseline's precision/recall is measured.
"""
import re
from typing import Optional

# (pattern, evidence_group): first group is the quoted evidence span.
CORRECTION_PATTERNS = [
    (re.compile(r"(?i)\bno\b.{0,30}?\buse\b(.{0,120})"), "no-use correction"),
    (re.compile(r"(?i)already told you(.{0,120})"), "repeated instruction"),
    (re.compile(r"(?i)\bnever\b.{0,40}?\b(use|do|run|commit|push)\b(.{0,120})"), "never-do constraint"),
    (re.compile(r"(?i)\bdon'?t\b.{0,40}?\b(use|do|run|commit|push)\b(.{0,120})"), "dont-do constraint"),
    (re.compile(r"(?i)\bwrong\b(.{0,120})"), "wrong-signal"),
    (re.compile(r"(?i)\bincorrect\b(.{0,120})"), "incorrect-signal"),
    (re.compile(r"(?i)\brevert that\b(.{0,120})"), "revert-signal"),
    (re.compile(r"(?i)\bi meant\b(.{0,120})"), "clarification"),
    (re.compile(r"(?i)\bnot\b.{0,20}?\b(use|like that|that way)\b(.{0,120})"), "negation"),
]

# Assistant-side failure signals that corroborate (not standalone corrections).
FAILURE_PATTERNS = [
    re.compile(r"\bFAILED\b|\bfailed\b"),
    re.compile(r"(?i)\berror\b.{0,40}?\btest\b|\btest\b.{0,40}?\berror\b"),
]


def classify_correction(text: str) -> Optional[dict]:
    """Return {kind, evidence} when text is an explicit correction, else None."""
    if not text or len(text) > 4000:
        if text and len(text) > 4000:
            text = text[:4000]
        elif not text:
            return None
    for rx, kind in CORRECTION_PATTERNS:
        m = rx.search(text)
        if m:
            span = m.group(0).strip()[:200]
            return {"kind": kind, "evidence": span, "source_text": text[:500]}
    return None


def has_failure_signal(text: str) -> bool:
    return any(rx.search(text) for rx in FAILURE_PATTERNS)
