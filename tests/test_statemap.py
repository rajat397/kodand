import time

from kodand.statemap import canonical_key, get_state, register_alias, resolve_entity
from kodand.store import Store


def _store(tmp):
    return Store(str(tmp))


def test_gate3_canonical_variants_merge(tmp_path):
    s = _store(tmp_path)
    s.remember("CLASS-CAP: 20 per week", locator="doc.md#0")
    s.remember("class cap: 15 per week", locator="doc.md#1")
    st = get_state(s, "class cap")
    assert st["entity"] == "class-cap"
    # both rows matched the same canonical node, recency resolves them
    assert "15 per week" in st["current"]["content"]


def test_gate3_temporal_truth(tmp_path):
    s = _store(tmp_path)
    t1 = time.time() - 86400  # yesterday
    t2 = time.time()
    row1 = s.remember("class-cap: 20 per week", locator="a.md#0")
    row2 = s.remember("class-cap: 15 per week (updated)", locator="a.md#1")
    # backdate rows: created_at must be <= as_of filters apply
    import sqlite3
    conn = sqlite3.connect(s.db_path)
    conn.execute("UPDATE memories SET created_at=?, updated_at=? WHERE id=?", (t1, t1, row1["key"]))
    conn.execute("UPDATE memories SET created_at=?, updated_at=? WHERE id=?", (t2, t2, row2["key"]))
    conn.commit(); conn.close()
    early = get_state(s, "class cap", as_of=t1 + 60)
    assert early is not None and "20 per week" in early["current"]["content"]
    now_state = get_state(s, "class cap")
    assert "15 per week" in now_state["current"]["content"]


def test_gate3_user_correction_wins_over_newer_capture(tmp_path):
    s = _store(tmp_path)
    cap1 = s.remember("class-cap: 20 per week", locator="a.md#0")["key"]
    time.sleep(0.02)
    _ = s.correct("class-cap: 15 per week (corrected)", replaces_id=cap1, origin="user")
    time.sleep(0.02)
    s.remember("class cap: 99 per week (model-made noise)", locator="a.md#2")
    st = get_state(s, "class cap")
    assert "15 per week (corrected)" in st["current"]["content"]
    assert st["current"]["authority"] == "correction"


def test_gate3_supersede_pointer_clean_chain(tmp_path):
    s = _store(tmp_path)
    r1 = s.remember("class-cap: 20", locator="a.md#0")["key"]
    time.sleep(0.02)
    r2 = s.remember("class-cap: 15", locator="a.md#1")["key"]
    s.supersede(r1, replaced_by=r2, reason="test")
    st = get_state(s, "class cap")
    assert "15" in st["current"]["content"]
    st_now = get_state(s, "class cap")
    assert "15" in st_now["current"]["content"]


def test_canonical_key():
    assert canonical_key("CLASS cap") == "class-cap"
    assert canonical_key("  class--cap!  ") == "class-cap"


def test_aliases_resolution(tmp_path):
    s = _store(tmp_path)
    s.remember("class cap is 20", locator="a.md#0")
    register_alias(s, "class-cap", "class size limits")
    assert resolve_entity(s, "class size limits") == "class-cap"
