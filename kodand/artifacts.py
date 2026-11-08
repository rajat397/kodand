"""K3: artifact ingest — memory about the files sessions actually touch.

Design (deep-roots track):
- every artifact is keyed by (uri, sha256); edits make a NEW version, never mutate
- chunk contents carry a provenance prefix "[artifact:<path>@<sha>]" so answers
  can cite where evidence came from, not just what it says
- re-ingesting a CHANGED file supersedes the OLD version's memory chunks via the
  K2 lifecycle (write-time supersede), so recall never returns stale versions
- idempotent: identical (uri, sha) pairs are no-ops
"""

from __future__ import annotations

import hashlib
import os
import re
from html.parser import HTMLParser
from pathlib import Path

CHUNK = 800
URI_SCHEME = "artifact:"


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("h1", "h2", "h3", "h4", "p", "br", "li", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in (".html", ".htm"):
        return "html"
    if ext in (".py", ".ts", ".js", ".tsx", ".go", ".rs", ".java", ".sh", ".json", ".yaml", ".yml", ".toml"):
        return "code"
    return "text"


def extract_text(path: Path) -> tuple[str, str]:
    """Return (kind, extractable text). Images return kind='image' with empty text."""
    kind = _kind_of(path)
    if kind == "image":
        return kind, ""
    if kind == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError("pdf extraction needs the extra: pip install 'kodand[pdf]'") from e
        try:
            reader = PdfReader(str(path))
            return kind, "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise RuntimeError(
                f"pdf extraction failed ({type(e).__name__}: {e}); "
                "try pip install 'kodand[pdf]' or repair the file") from e
    if kind == "html":
        parser = _HTMLText()
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
        return kind, re.sub(r"\n{2,}", "\n", "".join(parser.parts)).strip()
    return kind, path.read_text(encoding="utf-8", errors="replace")


def _chunks(text: str):
    for i in range(0, len(text), CHUNK):
        yield text[i : i + CHUNK].strip()


def ingest_artifact(store, repo: str, path: str, caption: str = "") -> dict:
    """Extract + register + remember one artifact. Idempotent per (uri, sha)."""
    src = Path(os.path.abspath(os.path.expanduser(path)))
    if not src.is_file():
        raise FileNotFoundError(f"artifact not found: {src}")
    sha = _sha256(src)
    kind, text = extract_text(src)
    conn = store._get_conn()
    row = conn.execute(
        "SELECT id FROM artifacts WHERE uri=? AND sha256=?",
        (str(src), sha),
    ).fetchone()
    conn.close()
    if row:
        return {"artifact_id": row[0], "sha256": sha, "status": "already-ingested", "chunks": 0}

    conn = store._get_conn()
    cur = conn.execute(
        "INSERT INTO artifacts (uri, sha256, kind, size, extraction, n_chunks, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(src), sha, kind, src.stat().st_size, "plain" if text else "none", 0,
         __import__("time").time()),
    )
    artifact_id = cur.lastrowid
    conn.commit()
    conn.close()

    # previous version chunks for the same uri (different sha) -> supersede (K2)
    prev_rows = [r for r in store.recall(URI_SCHEME + str(src), k=30)
                 if str(r.get("locator", "")).startswith(URI_SCHEME + str(src) + "@")
                 and not str(r.get("locator", "")).endswith("@" + sha)]
    prev_ids = [r["id"] for r in prev_rows]

    provenance = f"{URI_SCHEME}{src}@{sha}"
    chunks = 0
    sources = [("caption: " + caption, "text")] if caption else []
    if text:
        sources = sources + [(t, kind) for t in _chunks(text)]
    elif not caption:
        sources = [(f"image artifact (no text extraction; {src.stat().st_size} bytes)", "image")]
    for part, surface in sources:
        body = f"[{provenance}] {part}".strip()
        store.remember(body, surface=surface, locator=f"{provenance}#{chunks}")
        chunks += 1
    if chunks:
        conn = store._get_conn()
        conn.execute("UPDATE artifacts SET n_chunks=? WHERE id=?", (chunks, artifact_id))
        conn.commit()
        conn.close()
    for pid in prev_ids:
        store.supersede(pid, replaced_by=None, reason="newer-artifact-version")
    store.log_event("artifact-ingested", entry_id=None, provenance=provenance,
                    detail=json_sha(artifact_id, kind, chunks, sha))
    return {"artifact_id": artifact_id, "sha256": sha, "kind": kind, "chunks": chunks,
            "status": "ingested", "superseded_old": len(prev_ids)}


def json_sha(artifact_id, kind, chunks, sha) -> str:
    import json
    return json.dumps({"artifact_id": artifact_id, "kind": kind, "chunks": chunks, "sha256": sha[:16]})
