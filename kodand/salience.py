"""P7 salience gate: decide at capture what is worth remembering.

Rule-first (deterministic); laya-assist reserved for the borderline pass later
(sleep-time consolidation per D5). Tiers:

- "user"      — human-origin corrections and surface edits (D2: highest authority)
- "auto-high" — capture rows that match memory-relevant patterns (decisions,
                conventions, tooling, policies, artifact references)
- "auto-low"  — transcript chatter, greetings, generic talk (still stored and
                searchable; just never prioritized by the read path)

Everything is provenance-marked, nothing is dropped: the gate shapes ORDER, it
does not censor (D13, D18, and gate 3 of D4/D5 hold).
"""

from __future__ import annotations

import re

RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(ADR-\d+|decision|dpt-\w+)\b", re.IGNORECASE), "auto-high"),
    (re.compile(r"\b(must|convention|policy|rule|always|never\s+do)\b", re.IGNORECASE), "auto-high"),
    (re.compile(r"\b(uses|switched? to|migrated to|moved to|prefers|went with|chose)\s+\w+", re.IGNORECASE), "auto-high"),
    (re.compile(r"\b(build|deploy|track down|setup|schema|tc|toolchain|migration)\b", re.IGNORECASE), "auto-high"),
    (re.compile(r"\b(artifact|atlas|doc|log|migrations?|references?|sources?)\b", re.IGNORECASE), "auto-high"),
]

# never classified — immediate chatter (a fallback net; keep conservative)
CHAT = re.compile(r"\b(thanks|ok|cool|nice|great)\b[!.]?$", re.IGNORECASE)

TIERS = ("user", "pin", "auto-high", "auto-low")


def salience_of(content: str, memory_type: str = "reference", explicit: str | None = None) -> str:
    """Compute the salience tier for a row. explicit overrides (validated)."""
    if explicit is not None:
        if explicit not in TIERS:
            raise ValueError(f"invalid salience tier: {explicit!r} (allowed {TIERS})")
        return explicit
    if memory_type == "correction":
        return "user"
    if len(content) > 4000:  # long captures are more often background
        return "auto-low"
    for rx, tier in RULES:
        if rx.search(content):
            return tier
    if CHAT.search(content.strip()):
        return "auto-low"
    return "auto-low"
