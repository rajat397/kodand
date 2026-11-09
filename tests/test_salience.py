import pytest

from kodand.salience import salience_of
from kodand.store import Store


def _store(tmp):
    return Store(str(tmp))


def test_rules_high():
    assert salience_of("ADR-3: the recall engine must stay fcir") == "auto-high"
    assert salience_of("build uses bun and hoisted deps") == "auto-high"
    assert salience_of("convention: all tables snake_case") == "auto-high"


def test_chatter_low():
    assert salience_of("thanks!") == "auto-low"
    assert salience_of("ok cool", ) == "auto-low"


def test_corrections_are_user_tier():
    assert salience_of("whatever", memory_type="correction") == "user"


def test_explicit_overrides_validated():
    with pytest.raises(ValueError):
        salience_of("x", explicit="banana")
    assert salience_of("ok", explicit="pin") == "pin"


def test_store_persists_salience(tmp_path):
    s = _store(tmp_path)
    r1 = s.remember("ADR-5: the artifact registry is content-addressed")
    assert r1
    rows = s.list_memories()
    assert any(r.get("salience") == "auto-high" for r in rows)
    s.remember("thanks for reviewing", memory_type="correction")
    rows2 = s.list_memories()
    assert any(r.get("salience") == "user" for r in rows2)


def test_old_store_migrates(tmp_path):
    """Pre-v0.3 store: table without salience column; migration adds it."""
    import sqlite3
    db = tmp_path / ".kodand"
    db.mkdir()
    conn = sqlite3.connect(str(db / "bridge.db"))
    conn.execute("""CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, content TEXT,
        surface TEXT, locator TEXT, scope TEXT, session_id TEXT, created_at REAL,
        updated_at REAL, superseded_by INTEGER, content_hash TEXT, state TEXT DEFAULT 'active',
        memory_type TEXT)""")
    conn.execute("INSERT INTO memories(content, state) VALUES ('legacy note', 'active')")
    conn.commit(); conn.close()
    s = _store(tmp_path)
    s.remember("build uses bun and ADR-3 registers toolchain")
    rows = s.list_memories()
    tiers = [r.get("salience") for r in rows]
    assert "auto-high" in tiers and "auto-low" in tiers, tiers
