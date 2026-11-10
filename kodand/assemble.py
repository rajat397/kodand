"""K4: cache-aware block assembly for stateless LLMs.

Turn context into APPEND-ONLY, content-addressed memory blocks with an
immutable stable prefix, so provider-side KV/prompt caches hit across turns
instead of invalidating on every re-rank. Blocks:

- identity = sha256 of block text (content-addressed; position is never identity)
- order = frozen at first emission via the adapter's state file (slot table)
- appending never rewrites; invalidation is coarse (new text -> new block)
- the assembled prompt = stable prefix + frozen-order blocks + question
- kill switch: KODAND_BASELINE=1 => no memory blocks at all (plain FTS shards
  with an "unranked" marker), prefix hash still stable
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BLOCK_PREFIX_LEN = 90


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def block_id(text: str) -> str:
    return "blk_" + hashlib.sha256(text.strip().encode()).hexdigest()[:16]


def _block_from_memory(row: dict, slot: int) -> dict:
    """One block per context row (a session's best chunk or a BM25 seed).

    content-derived identity; text is row content (already provenance-tagged by
    K3 artifact ingest or K1 session mapping).
    """
    text = (row.get("content") or "").strip()
    head = " ".join(text.split())[:BLOCK_PREFIX_LEN]
    provenance = f"{row.get('sessionId', 'unknown')}#{row.get('entryId', '')}"
    body = f"[{head}] (memory {provenance}; p={row.get('session_p', row.get('laya_p') or 'n/a')})"
    return {
        "id": block_id(text + provenance),
        "slot": slot,
        "provenance": provenance,
        "content": text,
        "display": body,
    }


def load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass  # a corrupt state file restarts the session's slot table
    return {"order": {}, "prefix": None}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1, sort_keys=True))


def assemble(
    prefix: str,
    rows: list[dict],
    question: str,
    *,
    state_path: Path | None = None,
    kill_switch: bool = False,
    max_blocks: int = 10,
) -> dict:
    """Return assembled prompt + emitted blocks, honoring the frozen slot table.

    rows: provider recall output (sessionId/content/entryId/session_p/...)
    kill_switch: KODAND_BASELINE=1 honored in the assembly layer too.
    """
    blocks: list[dict] = []

    if not kill_switch:
        for row in rows[:max_blocks]:
            blocks.append(_block_from_memory(row, 0))  # slots assigned below

    state = load_state(state_path) if state_path else {"order": {}, "prefix": None}

    # prefix hash must be byte-identical across turns shows up in the gate
    prefix_hash = hashlib.sha256(prefix.strip().encode()).hexdigest()
    if state.get("prefix") and state["prefix"] != prefix_hash:
        raise RuntimeError("stable prefix changed mid-session; start a new session")

    # slot assignment is FROZEN at first emission (append-only rule)
    for b in blocks:
        known = state["order"].get(b["id"])
        if known is None:
            nxt = (max(state["order"].values()) + 1) if state["order"] else 0
            state["order"][b["id"]] = nxt
            known = nxt
        b["slot"] = known
    blocks.sort(key=lambda b: b["slot"])

    if state_path:
        state["prefix"] = prefix_hash
        save_state(state_path, state)

    memory_block_text = "\n".join(f"MEMORY-BLOCK[{b['slot']} {b['id']}]: {b['display']}" for b in blocks)
    assembled = (
        (prefix.rstrip() + "\n\n" if prefix.strip() else "")
        + (memory_block_text + "\n\n" if memory_block_text else "MEMORY-BLOCKS: none\n\n")
        + f"Question: {question}\nAnswer:"
    )
    return {
        "prefix_hash": prefix_hash,
        "blocks": [{"id": b["id"], "slot": b["slot"], "provenance": b["provenance"]} for b in blocks],
        "assembled": assembled,
        "assembled_sha256": hashlib.sha256(assembled.encode()).hexdigest()[:16],
        "kill_switch": kill_switch,
    }




def assemble_v2(
    prefix: str,
    rows: list[dict],
    question: str,
    *,
    entities: list[str] | None = None,
    store=None,
    state_path: Path | None = None,
    kill_switch: bool = False,
    max_blocks: int = 10,
) -> dict:
    """D4 state-blocks-first assembly (decision #4).

    Contract:
    1. every entity in `entities` emits exactly ONE STATE-BLOCK first — the D3
       value at now, with its authority visible.
    2. episodic blocks never displace a STATE-BLOCK unless the block budget is
       exhausted.
    3. KODAND_BASELINE=1 => the v1 row-block path byte-identical (kill_switch).
    4. a STATE-BLOCK id changes only when the graph changes (content-addressed);
       ranking reshuffles never touch it.
    """
    if kill_switch:
        return assemble(prefix, rows, question,
                        state_path=state_path, kill_switch=False, max_blocks=max_blocks)

    from kodand.statemap import get_state  # local import: no cycle

    # P7 no-pollution gate: episodic tail excludes auto-low rows (chatter) —
    # salience lives on the row (D2/D5), so the assembly can drop them honestly.
    if store is not None:
        c = store._get_conn()
        keep_sn = {r["id"] for r in c.execute(
            "SELECT id FROM memories WHERE salience NOT IN ('auto-low') OR memory_type='correction'").fetchall()}
        c.close()
        rows = [r for r in rows if isinstance(r.get("entryId"), int) and r["entryId"] in keep_sn]

    if state_path is not None and not isinstance(state_path, Path):
        state_path = Path(state_path)
    state = load_state(state_path) if state_path else {"order": {}, "prefix": None, "state_slots": {}}
    prefix_hash = hashlib.sha256(prefix.strip().encode()).hexdigest()
    if state.get("prefix") and state["prefix"] != prefix_hash:
        raise RuntimeError("stable prefix changed mid-session; start a new session")

    state_slots = state.setdefault("state_slots", {})
    blocks: list[dict] = []

    for ent in (entities or []):
        st = get_state(store, ent) if store else None
        if not st or not st.get("current"):
            continue
        cur = st["current"]
        text = (f"[STATE {ent}] {cur['content']} "
                f"(authority: {cur.get('authority','reference')}; memory #{cur.get('id')})")
        bid = block_id(text)
        slot = state_slots.get(bid)
        if slot is None:
            slot = len(state_slots)
            state_slots[bid] = slot
        blocks.append({"id": bid, "slot": slot, "provenance": f"state:{ent}",
                       "content": text, "display": text, "kind": "state"})

    # episodic tail: K4 v1 row-blocks, budget remaining after state blocks
    remain = max(0, max_blocks - len(blocks))
    episodic = [_block_from_memory(row, 0) for row in rows[:remain]]
    ep_state = {"order": state.get("order", {})}
    known = ep_state["order"]
    for b in episodic:
        known_s = known.get(b["id"])
        if known_s is None:
            nxt = (max(known.values()) + 1) if known else 0
            known[b["id"]] = known_s = nxt
        b["slot"] = known_s
    state["order"] = known
    episodic.sort(key=lambda b: b["slot"])
    for b in episodic:
        b["kind"] = "episodic"
    blocks += episodic

    if state_path:
        state["prefix"] = prefix_hash
        save_state(state_path, state)

    memory_block_text = "\n".join(
        f"MEMORY-BLOCK[{b['slot']} {b['id']}|{b.get('kind','episodic')}]: {b['display']}"
        for b in blocks)
    assembled = (
        (prefix.rstrip() + "\n\n" if prefix.strip() else "")
        + (memory_block_text + "\n\n" if memory_block_text else "MEMORY-BLOCKS: none\n\n")
        + f"Question: {question}\nAnswer:"
    )
    return {
        "prefix_hash": prefix_hash,
        "blocks": [{"id": b["id"], "slot": b["slot"], "provenance": b["provenance"],
                    "kind": b.get("kind", "episodic")} for b in blocks],
        "assembled": assembled,
        "assembled_sha256": hashlib.sha256(assembled.encode()).hexdigest()[:16],
        "kill_switch": False,
    }
