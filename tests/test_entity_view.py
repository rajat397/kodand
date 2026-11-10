"""K5 entity-view gates (decision #7): data-truth + card fields from store."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "docs"))

from kodand.store import Store
from kodand.surface import MemoryService


def _svc(tmp):
    s = Store(str(tmp))
    s.remember("toolchain: bun with hoisted deps", locator="a.md#0")
    s.remember("toolchain: pnpm for legacy", locator="a.md#1")
    s.correct("toolchain: bun only (corrected)", replaces_id=None, origin="user")
    return MemoryService(str(tmp))


def test_g1_entities_from_store(tmp_path):
    svc = _svc(tmp_path)
    ents = svc.entities()["entities"]
    assert any(e["entity"] == "toolchain" for e in ents)
    t = next(e for e in ents if e["entity"] == "toolchain")
    assert t["rows"] >= 2 and "correction" in (t.get("authorities") or [])


def test_g1_state_endpoint_data_truth(tmp_path):
    svc = _svc(tmp_path)
    st = svc.state("toolchain")
    assert st["entity"] == "toolchain"
    # authority wins: the user correction is the current value
    assert "corrected" in (st["current"] or {}).get("content", "")
    assert (st["current"] or {}).get("authority") == "correction"


def test_g1_no_mock_rows(tmp_path):
    empty = tempfile.mkdtemp()
    svc = MemoryService(empty)  # NO seeding: assert empty store -> empty surface, no fixtures
    assert svc.entities()["entities"] == []
