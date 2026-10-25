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

# Deterministic session summarizer: first user msg + last assistant msg + entity list
def summarize_session(messages: List[Dict]) -> str:
    if not messages:
        return ""
    first = next((m["content"][:120] for m in messages if m["role"] == "user"), "")
    last = next((m["content"][:120] for m in reversed(messages) if m["role"] == "assistant"), "")
    # entity hint: comma lists after like/including
    all_content = " ".join(m["content"] for m in messages)
    entities = []
    for pat in [r"like\s+([^.\n]{10,120})", r"including\s+([^.\n]{10,120})"]:
        for m in re.finditer(pat, all_content, re.I):
            chunk = m.group(1).split("\n")[0][:100]
            for part in re.split(r",| and ", chunk):
                c = part.strip()
                if 2 < len(c) < 40 and c[0].isupper():
                    entities.append(c)
                    if len(entities) >= 4:
                        break
    ent_str = ", ".join(entities[:3]) if entities else ""
    return f"{first} | {last} | entities: {ent_str}".strip()[:400]

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
        # use entry lookup by locator for linking triples; here we create triples for each chunk's content
        # triples are attached to session, not yet to entry_id (entry_id resolved via locator after bulk ingest)
        for t in extract_okf_triples(m["content"], 0, session_id):
            # store with entry_id 0 for now, will be backfilled via locator if needed
            try:
                store.add_okf_triple(0, session_id, t["subject"], t["predicate"], t["object"], t["confidence"])
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
