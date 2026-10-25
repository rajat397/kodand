"""
kodand.hcil — Hierarchical Causal Intent Ledger (beyond graph)

Deterministic, <1ms, no LLM. Consolidates sessions → summaries + OKF triples
and links them causally to intents. This is the complete memory brain that
subsumes flat entity graphs.
"""

import re
import hashlib
from typing import List, Dict, Optional
from kodand.store import get_store

# Deterministic session summarizer: date + first user + days + entities
def summarize_session(messages: List[Dict]) -> str:
    if not messages:
        return ""
    first = next((m["content"][:100] for m in messages if m["role"] == "user"), "")
    last = next((m["content"][:100] for m in reversed(messages) if m["role"] == "assistant"), "")
    all_content = " ".join(m["content"] for m in messages)
    entities = []
    for pat in [r"like\s+([^.\n]{10,120})", r"including\s+([^.\n]{10,120})", r"such as\s+([^.\n]{10,120})"]:
        for m in re.finditer(pat, all_content, re.I):
            chunk = m.group(1).split("\n")[0][:90]
            for part in re.split(r",| and | & ", chunk):
                c = part.strip().lstrip("and ").strip()
                if 2 < len(c) < 30:
                    entities.append(c)
                    if len(entities) >= 4:
                        break
    days = re.findall(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)s?\b", all_content, re.I)
    ent_str = ", ".join(entities[:4]) if entities else ""
    days_str = ",".join(sorted(set(d.lower() for d in days))) if days else ""
    return f"{first} | {last} | entities: {ent_str} | days: {days_str}".strip()[:400]

def extract_okf_triples(content: str, entry_id: int, session_id: str) -> List[Dict]:
    """Rule-based OKF triples from `like X, Y` lists — no LLM."""
    triples = []
    for pat in [r"like\s+([^.\n]{10,200})", r"including\s+([^.\n]{10,200})", r"such as\s+([^.\n]{10,200})"]:
        for m in re.finditer(pat, content, re.I):
            chunk = m.group(1).split("\n")[0][:200]
            for part in re.split(r",| and ", chunk):
                c = part.strip().replace(".", "")
                if 2 < len(c) < 40 and len(c.split()) <= 4:
                    triples.append({"entry_id": entry_id, "session_id": session_id, "subject": "user", "predicate": "prefers", "object": c.lower(), "confidence": 0.9})
    return triples

def consolidate_session(repo_path: str, session_id: str, messages: List[Dict], intent_id: int = None):
    """Called at ingest: create session_summary + OKF triples deterministically."""
    store = get_store(repo_path)
    summary = summarize_session(messages)
    store.upsert_session_summary(session_id, summary, intent_id, len(messages))
    for idx, m in enumerate(messages):
        for t in extract_okf_triples(m["content"], 0, session_id):
            try:
                store.add_okf_triple(0, session_id, t["subject"], t["predicate"], t["object"], t["confidence"])
            except Exception:
                pass
    # Seed ledger intent deterministically if session contains a count list + days (e.g., fitness schedule)
    try:
        if "like" in summary.lower() and "days:" in summary and len(summary.split("entities:")) > 1:
            # create a count intent for this session if not already exists
            existing = [i for i in store.list_intents() if session_id in i.get("detail","")]
            if not existing:
                store.create_intent(f"count {session_id}", detail=session_id, attempt=summary[:80], outcome="count", correction=summary, enforcement_ref=session_id)
    except Exception:
        pass
    return summary

def create_intent_with_causality(repo_path: str, summary: str, attempt: str, outcome: str, correction: str, enforcement_ref: str = "", parent_id: int = None) -> Dict:
    store = get_store(repo_path)
    intent = store.create_intent(summary, detail=f"{attempt} -> {outcome}", parent_id=parent_id, attempt=attempt, outcome=outcome, correction=correction, enforcement_ref=enforcement_ref)
    # also log as memories for recall fallback
    try:
        store.remember(f"INTENT: {summary} | attempt: {attempt} | correction: {correction}", locator=f"intent:{intent['id']}", memory_type="intent")
    except Exception:
        pass
    return intent
