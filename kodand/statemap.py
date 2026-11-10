"""D3 statemap: temporal entity-state reads over the memory graph.

From decisions #3 (read model), applied per spine (root cause P2/P5):
- reads answer "what does the agent believe about ENTITY X at time T" — not
  "which chunks look similar"
- entity keys are deterministic (typed, canonicalized): lowercase, alnum+dash;
  learned NER is the fallback ladder, never the core (gate: no LLM in state path)
- truth comes from the graph the store already is: `memories` rows, their
  `created_at` (state valid-from), `superseded_by` pointer edges, and
  `memory_type` authority (D2: correction > reference)

Public:
  canonical_key(phrase)          -> typed key (deterministic normalization)
  register_alias(store, key, alias)
  resolve_entity(store, phrase)  -> canonical key or None
  get_state(store, phrase, as_of=None) -> {"entity", "as_of", "current", "past"}

`as_of` is a unix-second upper bound; None means "now". `current` = the value the
graph supports at that time for the highest-authority chain; `timeline` shows
every row of that chain with its authority superseded-state at that time.
"""

from __future__ import annotations

import re

CANON = re.compile(r"[^a-z0-9]+")


def canonical_key(phrase: str) -> str | None:
    v = (phrase or "").strip().lower()
    key = CANON.sub("-", v).strip("-")
    return key or None


AUTH_IN_STATE = {"correction": 3, "reference": 1}
CHATTER = re.compile(r"\b(thanks|ok|cool)\b[!.]?$", re.IGNORECASE)


def _rows_for(store, entity: str, as_of: float | None) -> list[dict]:
    """All rows for the canonical key, with any variant alias forms."""
    variants = [entity]
    conn = store._get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS aliases (entity TEXT, alias TEXT, UNIQUE(entity, alias))")
    rows = [dict(r) for r in conn.execute(
        "SELECT alias FROM aliases WHERE entity=?", (entity,)).fetchall()]
    variants += [r["alias"] for r in rows]
    # dash/space invariant: 'class-cap' and 'class cap' and 'CLASS_CAP' are one node
    spaced = entity.replace("-", " ")
    variants += [spaced, spaced.upper()]
    out: dict[int, dict] = {}
    conn = store._get_conn()
    try:
        seen: set[int] = set()
        for v in variants:
            v = v.lower()
            # sqlite LIKE has no []-classes: dash and space variants are separate
            # patterns, and '_' in LIKE is a single-char wildcard (harmless here).
            variants_forms = {
                v,                      # canonical dash form (keys use dashes)
                v.replace("-", " "),    # human spaced form
            }
            for variant in variants_forms:
                pattern = f"%{variant}%"
                found = conn.execute(
                    "SELECT id, content, created_at, updated_at, memory_type, state, superseded_by "
                    "FROM memories WHERE (locator LIKE ? OR content LIKE ?) AND state IN ('active','superseded') "
                    "ORDER BY id",
                    (pattern, pattern)).fetchall()
                for r in found:
                    d = dict(r)
                    if d["id"] in seen:
                        continue
                    seen.add(d["id"])
                    if as_of is not None and d["created_at"] > as_of:
                        continue
                    out[d["id"]] = d
    finally:
        conn.close()
    ordered = sorted(out.values(), key=lambda r: r["id"])
    return ordered


def _authority(memory_type: str) -> int:
    return AUTH_IN_STATE.get(memory_type or "reference", 0)


def get_state(store, phrase: str, as_of: float | None = None) -> dict | None:
    entity = resolve_entity(store, phrase) or canonical_key(phrase)
    if not entity:
        return None
    rows = _rows_for(store, entity, as_of)
    if not rows:
        return {"entity": entity, "as_of": as_of, "current": None,
                "timeline": [], "chains": []}

    # terminal-of-chain: supersede pointers say row A was retired in favor of B
    superseded = {r["id"]: r["superseded_by"] for r in rows if r["superseded_by"]}

    def authority(r) -> int:
        return _authority(r["memory_type"])

    def fresh(r):
        return (r["updated_at"] or r["created_at"] or 0)

    # chain: exclude rows whose superseder is in the set (they are retired versions)
    active_ = [r for r in rows
               if r["superseded_by"] is None or r["superseded_by"] not in {x["id"]: 1 for x in rows}]
    # authority wins (D2), recency only inside the same authority class
    active_.sort(key=lambda r: (-authority(r), -fresh(r), -r["id"]))
    current = active_[0] if active_ else None

    timeline = [
        {"id": r["id"], "content": r["content"], "state": r["state"],
         "authority": r["memory_type"], "created_at": r["created_at"],
         "superseded_by": r["superseded_by"]}
        for r in rows
    ]
    return {
        "entity": entity,
        "as_of": as_of,
        "current": ({"id": current["id"], "content": current["content"],
                     "authority": current["memory_type"]}
                    if current else None),
        "timeline": timeline,
        "chains": sorted(superseded.keys()),
    }


def register_alias(store, entity: str, alias: str) -> bool:
    entity = canonical_key(entity)
    alias = (alias or "").strip().lower()
    if not entity or not alias:
        return False
    conn = store._get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS aliases (entity TEXT, alias TEXT, UNIQUE(entity, alias))")
    conn.execute("INSERT OR IGNORE INTO aliases(entity, alias) VALUES (?, ?)",
                 (entity, alias))
    conn.commit()
    conn.close()
    return True


def resolve_entity(store, phrase: str) -> str | None:
    """Alias table first (exact lowercase), then canonical fallback."""
    p = (phrase or "").strip().lower()
    if not p:
        return None
    conn = store._get_conn()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS aliases (entity TEXT, alias TEXT, UNIQUE(entity, alias))")
        row = conn.execute("SELECT entity FROM aliases WHERE alias=? LIMIT 1", (p,)).fetchone()
        if row:
            return row["entity"]
    finally:
        conn.close()
    return canonical_key(phrase)
