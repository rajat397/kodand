"""P7 read-gate verification: proactive surfacing without pollution."""
import tempfile

from kodand.assemble import assemble_v2
from kodand.statemap import turn_entities
from kodand.store import Store


def _seed(tmp):
    s = Store(str(tmp))
    s.remember("toolchain: bun with hoisted deps", locator="a.md#0")
    s.correct("toolchain: bun only (corrected)", replaces_id=None, origin="user")
    # 10 irrelevant auto-captured chatter rows
    for i in range(10):
        s.remember(f"misc note {i}: thanks cool vibes Zusammenarbeit", locator=f"x{i}.md#0")
    return s


def test_rows_derive_entities_deterministically(tmp_path):
    s = _seed(tmp_path)
    rows = [{"sessionId": "a.md", "entryId": 1, "content": "build uses toolchain: bun"}]
    ents = turn_entities(s, "build tool cheat sheet?", rows)
    assert ents and ents[0] == "toolchain"
    # determinism: reshuffled rows -> same pick
    ents2 = turn_entities(s, "build tool cheat sheet?", list(reversed(rows)))
    assert ents2 == ents


def test_gate_no_pollution(tmp_path):
    s = _seed(tmp_path)
    rows = [{"sessionId": "a.md", "entryId": 1, "content": "toolchain: bun is the setup"},
            *[{"sessionId": f"x{i}.md", "entryId": i + 2,
               "content": f"misc note {i}: chatter"} for i in range(6)]]
    ents = turn_entities(s, "what is the toolchain?", rows)
    out = assemble_v2("SYS-pfx", rows, "what is the toolchain?", entities=ents,
                      store=s, state_path=tmp_path / "s.json", max_blocks=6)
    assembled = out["assembled"]
    assert "STATE toolchain" in assembled and "bun only (corrected)" in assembled
    # irrelevant auto-captures must not appear in the assembled prompt
    assert "misc note 3" not in assembled and "misc note 6" not in assembled


def test_gate_recall_hit(tmp_path):
    s = _seed(tmp_path)
    # a past-session fact: created in an EARLIER session, not repeated in question
    rows = [{"sessionId": "a.md", "entryId": 1, "content": "toolchain: bun is the setup"}]
    ents = turn_entities(s, "what is the toolchain?", rows)
    out = assemble_v2("SYS", rows, "what is the toolchain?", entities=ents, store=s,
                      state_path=tmp_path / "s.json")
    # the correction (user-authored past-session fact) is surfaced in the prompt
    assert "bun only (corrected)" in out["assembled"]


def test_turn_entities_empty_store(tmp_path):
    s = Store(tempfile.mkdtemp())
    assert turn_entities(s, "anything about pricing?", []) == []
