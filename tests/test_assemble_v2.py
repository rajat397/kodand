

from kodand.assemble import assemble_v2
from kodand.store import Store


def _rows():
    return [
        {"sessionId": "q1-session-2", "entryId": 41, "content": "build uses bun",
         "session_p": 0.86},
        {"sessionId": "q1-session-9", "entryId": 77, "content": "build uses npm",
         "session_p": 0.84},
    ]


def test_gate1_state_block_first(tmp_path):
    s = Store(str(tmp_path))
    s.remember("MODEL-MADE noise about build tool", locator="a.md#2")
    _ = s.correct("repo.toolchain: bun (user-corrected)", replaces_id=None, origin="user")
    out = assemble_v2("SYS", _rows(), "what build tool?",
                      entities=["repo.toolchain"], store=s,
                      state_path=tmp_path / "s.json")
    blocks = out["blocks"]
    assert blocks and blocks[0]["kind"] == "state"
    assert blocks[0]["provenance"] == "state:repo.toolchain"
    assert "bun" in blocks[0].get("display", "") or "bun" in str(out["assembled"]).lower()
    assert "[STATE" in out["assembled"]


def test_gate2_episodic_never_displaces_state(tmp_path):
    s = Store(str(tmp_path))
    _ = s.correct("repo.toolchain: bun (user-corrected)", replaces_id=None, origin="user")
    many = _rows() * 3  # 6 episodic candidates > budget 10 minus state
    out = assemble_v2("SYS", many[:6], "build tool?", entities=["repo.toolchain"],
                      store=s, state_path=tmp_path / "s.json", max_blocks=4)
    kinds = [b["kind"] for b in out["blocks"]]
    assert kinds[0] == "state"
    assert set(kinds) <= {"state", "episodic"}
    assert sum(1 for b in out["blocks"] if b["kind"] == "state") == 1


def test_gate3_kill_switch_v1_identical(tmp_path):
    s = Store(str(tmp_path))
    rows = _rows()
    legacy = assemble_v2("SYS", rows, "q?", store=s,
                         state_path=tmp_path / "a.json", kill_switch=True, max_blocks=10)
    v1 = __import__("kodand.assemble", fromlist=["assemble"]).assemble(
        "SYS", rows, "q?", state_path=tmp_path / "b.json", max_blocks=10)
    assert legacy["assembled"] == v1["assembled"]


def test_gate4_state_id_changes_only_with_graph(tmp_path):
    s = Store(str(tmp_path))
    _ = s.correct("repo.toolchain: bun (user-corrected)", replaces_id=None, origin="user")
    state_path = tmp_path / "s.json"
    o1 = assemble_v2("SYS", _rows(), "q1", entities=["repo.toolchain"], store=s,
                     state_path=state_path)
    o2 = assemble_v2("SYS", list(reversed(_rows())), "q2", entities=["repo.toolchain"],
                     store=s, state_path=state_path)  # reshuffled episodic order
    state_ids_1 = [b["id"] for b in o1["blocks"] if b["kind"] == "state"]
    state_ids_2 = [b["id"] for b in o2["blocks"] if b["kind"] == "state"]
    assert state_ids_1 == state_ids_2, "state-block id is content-addressed"
    assert o1["prefix_hash"] == o2["prefix_hash"]
