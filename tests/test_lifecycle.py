import json
import pytest


def _store(tmp):
    from kodand.store import Store

    return Store(str(tmp))


def test_supersede_removes_from_default_recall_and_keeps_provenance(tmp_path):
    s = _store(tmp_path)
    old = s.remember("the project uses npm", locator="l#0")["key"]
    hits = s.recall("npm", k=5)
    assert any(h["id"] == old for h in hits)

    assert s.supersede(old, reason="test")

    assert not any(h["id"] == old for h in s.recall("npm", k=5))
    chain = [r["state"] for r in s.list_memories_with_supersede_chain(old)]
    assert "superseded" in chain
    events = [e for e in s.get_events(kind="superseded")]
    assert any(e["entry_id"] == old for e in events)


def test_correct_supersedes_and_logs_origin(tmp_path):
    s = _store(tmp_path)
    old = s.remember("build uses npm", locator="l#0")["key"]
    new = s.correct("build uses bun", replaces_id=old, origin="user")["key"]
    rec = s.recall("build", k=5)
    assert all(h["id"] != old for h in rec)
    assert any(h["id"] == new and h["memory_type"] == "correction" for h in rec)
    corrections = s.get_events(kind="correction")
    assert any(e["provenance"] == "user" for e in corrections)


def test_recall_respects_lifecycle(tmp_path):
    s = _store(tmp_path)
    a = s.remember("v1: sodium 3g per serving", locator="l#0")["key"]
    b = s.remember("v2: sodium 5g per serving", locator="l#0")["key"]
    s.supersede(a, replaced_by=b, reason="newer-label")
    hits = s.recall("sodium", k=10)
    assert [h["id"] for h in hits if "sodium" in h["content"]] == [b]
