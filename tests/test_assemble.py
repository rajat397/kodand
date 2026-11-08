import hashlib
import json
from pathlib import Path

import pytest

from kodand.assemble import assemble, block_id, load_state


def _rows():
    return [
        {"sessionId": "q1-session-2", "entryId": 41, "content": "build uses bun",
         "session_p": 0.86},
        {"sessionId": "q1-session-9", "entryId": 77, "content": "build uses npm",
         "session_p": 0.84},
    ]


def test_gate1_same_input_same_blocks_and_assembled(tmp_path):
    a1 = assemble(prefix="SYS", rows=_rows(), question="build tool?", state_path=tmp_path / "s.json")
    a2 = assemble(prefix="SYS", rows=_rows(), question="build tool?", state_path=tmp_path / "s.json")
    assert a1["blocks"] == a2["blocks"]
    assert a1["assembled_sha256"] == a2["assembled_sha256"]
    ids = [b["id"] for b in a1["blocks"]]
    assert ids == [block_id("build uses bun" + "q1-session-2#41"),
                   block_id("build uses npm" + "q1-session-9#77")]


def test_gate2_new_chunk_appends_without_moving_prefix(tmp_path):
    state = tmp_path / "state.json"
    first = assemble(prefix="SYS", rows=_rows(), question="build tool?", state_path=state)
    before = first["blocks"]
    rows3 = _rows() + [{"sessionId": "q1-session-3", "entryId": 99, "content": "bun hoists deps"}]
    second = assemble(prefix="SYS", rows=rows3, question="build tool?", state_path=state)
    assert second["prefix_hash"] == first["prefix_hash"]
    assert second["blocks"][:2] == before
    assert len(second["blocks"]) == 3
    # append-only: assembled is the previous one plus the delta block text
    delta_only = second["assembled"].replace(first["assembled"].replace("Answer:", ""), "")
    assert "q1-session-3#99" in delta_only


def test_gate3_reordering_does_not_mutate_emitted_ids(tmp_path):
    state = tmp_path / "s.json"
    rows = [_rows()[1], _rows()[0]]  # reversed input order
    r = assemble(prefix="SYS", rows=rows, question="build tool?", state_path=state)
    # content-keyed identity: reversed order still yields the same block ids
    ids = {b["id"] for b in r["blocks"]}
    assert ids == {block_id("build uses bun" + "q1-session-2#41"),
                   block_id("build uses npm" + "q1-session-9#77")}


def test_gate4_kill_switch_serves_no_memory_blocks(tmp_path):
    r = assemble(prefix="SYS", rows=_rows(), question="build tool?",
                 kill_switch=True, state_path=tmp_path / "k.json")
    assert r["kill_switch"] is True and r["blocks"] == []
    assert "MEMORY-BLOCKS: none" in r["assembled"]


def test_prefix_shift_is_a_hard_error(tmp_path):
    state = tmp_path / "s.json"
    assemble(prefix="SYS-v1", rows=_rows(), question="q", state_path=state)
    with pytest.raises(RuntimeError, match="stable prefix changed"):
        assemble(prefix="SYS-v2", rows=_rows(), question="q", state_path=state)
