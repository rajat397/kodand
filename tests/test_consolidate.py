import json
import multiprocessing
import time
from pathlib import Path

import pytest

from kodand.assemble import assemble
from kodand.consolidate import list_pending, propose, resolve
from kodand.store import Store


def _store(tmp):
    s = Store(str(tmp))
    # seed rows: two same-topic captures (locators collapse), one foreign topic
    s.remember("ADR-1 the recall engine ships with bun", locator="repo.md#0")
    s.remember("the recall engine now ships with native bun support", locator="repo.md#1")
    s.remember("weather was lovely on the ski trip", locator="trip.md#0")
    return s


def test_d5_gate1_idempotence(tmp_path):
    s = _store(tmp_path)
    r1 = propose(s)
    r2 = propose(s)
    assert r1["status"] == "ok"
    assert r2["queued"] == 0, "second run must enqueue nothing (gate 2)"
    assert list_pending(s), "some proposals exist from run 1"


def test_d5_gate2_cursor_sweep(tmp_path):
    s = _store(tmp_path)
    propose(s)
    # new row after cursor: next pass only scans it
    s.remember("another note about the recall engine", locator="repo.md#2")
    r = propose(s)
    assert r["scanned"] == 1
    assert r["queued"] >= 1


def test_d5_gate3_race_guard(tmp_path):
    """Two concurrent consolidate invocations: only one runs (flock)."""
    s = _store(tmp_path)
    import fcntl

    from kodand.consolidate import _SweptLock
    lock = _SweptLock(str(tmp_path))
    assert lock.acquired  # we hold it
    r = propose(s)
    assert r["status"] == "busy", "a second worker must not interleave"
    lock.release()
    r2 = propose(s)
    assert r2["status"] == "ok"


def test_d5_gate4_authority_unchanged(tmp_path):
    """Queue writes never touch memory rows or their authority/state."""
    s = _store(tmp_path)
    before = {r["id"]: r["state"] for r in s.list_memories()}
    propose(s)
    after = {r["id"]: r["state"] for r in s.list_memories()}
    assert before == after  # no state mutation from the batch


def test_d5_gate5_resolve_and_event(tmp_path):
    s = _store(tmp_path)
    propose(s)
    qid = list_pending(s)[0]["id"]
    out = resolve(s, qid, "merged")
    assert out["resolved"]
    cls = [e for e in s.get_events(kind="merge-resolved")]
    assert any(json.loads(e["detail"])["queue_id"] == qid for e in cls)
    assert all(q["id"] != qid for q in list_pending(s))


def test_d4_prefix_invariance_across_batches(tmp_path):
    """Batch runs that only enqueue proposals never change the assembled hash."""
    state = tmp_path / "asm-state.json"
    from kodand.assemble import assemble
    s = _store(tmp_path)
    rows = [{"sessionId": "r1", "entryId": 1, "content": "build uses bun"}]
    a1 = assemble("SYS-pfx", rows, "what build tool?", state_path=state)
    propose(s)  # enqueues proposals (no state change)
    a2 = assemble("SYS-pfx", rows, "what build tool?", state_path=state)
    assert a1["assembled_sha256"] == a2["assembled_sha256"], "prefix/hash unaffected by batch"
