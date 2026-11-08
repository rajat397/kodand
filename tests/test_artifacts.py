import json
import hashlib
from pathlib import Path
import pytest

from kodand.store import Store
from kodand.artifacts import ingest_artifact, extract_text


def _repo(tmp):
    return Store(str(tmp))


def test_markdown_artifact_ingests_with_provenance(tmp_path):
    repo = tmp_path / "repo"
    s = _repo(repo)
    f = tmp_path / "notes.md"
    f.write_text("# Title\n\nuses bun and hoisted deps for the build.")
    r = ingest_artifact(s, str(repo), str(f))
    assert r["status"] == "ingested" and r["chunks"] >= 1
    hits = s.recall("bun hoisted deps", k=5)
    assert hits, "artifact chunks must be recallable"
    assert any(r["locator"].startswith("artifact:") for r in hits)
    # provenance prefix travels with content for grounded answers
    assert any(h["content"].startswith("[artifact:") for h in hits)


def test_idempotent_same_sha(tmp_path):
    repo = tmp_path / "repo"
    s = _repo(repo)
    f = tmp_path / "steel.md"
    f.write_text("a trustworthy note about steel production")
    r1 = ingest_artifact(s, str(repo), str(f))
    r2 = ingest_artifact(s, str(repo), str(f))
    assert r1["status"] == "ingested" and r2["status"] == "already-ingested"


def test_edited_artifact_supersedes_old_version(tmp_path):
    repo = tmp_path / "repo"
    s = _repo(repo)
    f = tmp_path / "policy.md"
    f.write_text("Version 1 statement: class size cap is 20")
    r1 = ingest_artifact(s, str(repo), str(f))
    old_ids = [h["id"] for h in s.recall("class size cap", k=30)]
    assert old_ids
    # edit + re-ingest -> new sha
    f.write_text("Version 2 statement: class size cap is 15")
    r2 = ingest_artifact(s, str(repo), str(f))
    assert r2["sha256"] != r1["sha256"]
    rec = s.recall("class size cap", k=30)
    alive = [h for h in rec if "sodium" not in content_of(h)]
    assert all("Version 1 statement" not in content_of(h) for h in alive), "old chunks superseded"
    assert any("Version 2 statement" in content_of(h) for h in alive), "new chunks active"
    superseded_events = s.get_events(kind="superseded")
    assert superseded_events, "K2 lifecycle writes the journal"


def content_of(h):
    return h.get("content", "")


def test_html_extraction_strips_script_and_style(tmp_path):
    f = tmp_path / "page.html"
    f.write_text("<html><body><p>Serving invite-only beta from April</p>"
                 "<style>.x{color:blue}</style><script>var leak=1</script></body></html>")
    kind, text = extract_text(f)
    assert kind == "html"
    assert "beta" in text and "color:blue" not in text and "leak" not in text


def test_pdf_without_extra_raises_hint(tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.7 fake")
    try:
        extract_text(f)
    except RuntimeError as e:
        assert "kodand[pdf]" in str(e)
    except ImportError as e:
        assert "pypdf" in str(e)
    else:
        pytest.skip("pypdf installed; extraction proceeded")


def test_image_artifact_gets_provenance_chunk_from_caption(tmp_path):
    repo = tmp_path / "repo"
    s = _repo(repo)
    img = tmp_path / "whiteboard.png"
    img.write_bytes(b"\x89PNG fake-bytes")
    r = ingest_artifact(s, str(repo), str(img), caption="whiteboard session photo")
    rec = s.recall("whiteboard photo", k=5)
    assert any("caption: whiteboard session photo" in content_of(h) for h in rec)
    assert all(str(r["sha256"],) == str(hashlib.sha256(img.read_bytes()).hexdigest(),) for h in rec[:1])
