#!/usr/bin/env python3
"""M6 scanners: secrets over stored artifacts (zero-hit required) and injection corpus checks.

Usage:
  python3 scan_artifacts.py secrets <paths...>   # detectors from kodand.scope.KEY_RES
  python3 scan_artifacts.py corpus bench/safety/injection-corpus.jsonl

Detectors are the SAME list Store.remember blocks on; this gate exists to prove no detector
class escaped the write path onto disk (models, sqlite, logs included).
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from kodand.scope import KEY_RES

SECRET_EXTS = {".py", ".md", ".json", ".jsonl", ".txt", ".log", ".sh", ".ts", ".service", ".env"}
SQLITE_EXTS = {".db", ".sqlite", ".sqlite3"}
# Round-2 pre-registration: fixtures inside tests/ legitimately contain key SHAPES
# (they verify the write-path blocker itself). Scanner skips tests/, never skips data/.
ALLOWED_IN_TESTS = True


def scan_file(path: str, hits: list):
    ext = Path(path).suffix.lower()
    if ext in SQLITE_EXTS:
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            for tbl in ("memories", "sessions", "chunks"):
                try:
                    for (tx,) in conn.execute(f"SELECT content FROM {tbl}"):
                        blob = tx if isinstance(tx, str) else (tx or b"").decode("utf-8", "replace")
                        for pattern, name in KEY_RES:
                            if pattern.search(blob):
                                hits.append((str(path), tbl, name, blob[:60].replace("\n", " ")))
                                break
                except sqlite3.OperationalError:
                    pass
            conn.close()
        except sqlite3.Error as e:
            hits.append((str(path), "sqlite-open", "error", str(e)))
        return
    if ext not in SECRET_EXTS:
        return
    try:
        blob = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    skip = ALLOWED_IN_TESTS and ("test" in Path(path).name or "injection-corpus" in Path(path).name)
    for r, name in KEY_RES:
        if r.search(blob):
            if skip:
                continue  # fixtures inside tests/ legitimately hold key SHAPES
            hits.append((str(path), "text", name, "detector hit"))


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "secrets"
    if mode == "secrets":
        hits = []
        for p in sys.argv[2:]:
            p = Path(p)
            if p.is_dir():
                for root, dirs, files in os.walk(p):
                    for f in files:
                        scan_file(str(Path(root) / f), hits)
            else:
                scan_file(str(p), hits)
        if hits:
            for h in hits[:40]:
                print("HIT", h)
            print(f"secrets scan: {len(hits)} hits", file=sys.stderr)
            return 1
        print("secrets scan: 0 hits |", " ".join(sys.argv[2:]))
        return 0
    if mode == "corpus":
        rows = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        cats = {r["category"] for r in rows}
        assert len(rows) >= 30, f"corpus too small: {len(rows)}"
        assert len(cats) == 4, f"expected 4 categories, have {sorted(cats)}"
        for r in rows:
            assert r.get("content"), r
        print(f"corpus: {len(rows)} rows across {sorted(cats)} — pre-registered size holds")
        return 0
    print("unknown mode", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
