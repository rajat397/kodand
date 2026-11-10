"""K5: the memory surface — Kodand's visual, interactive, correction-capable UI.

An HTTP surface (stdlib only, localhost-only by default) that binds the approved
K5 design (docs/k5-memory-surface.html) to the real Store:

G1 data-truth    : every visible row comes from store JSON, nothing hardcoded
G2 write-back    : corrections/supersede in the UI use Store.correct(origin=user)
                   and Store.supersede, so events with provenance land on disk
G3 assembly view : shows the K4 block ids+slots the next agent prompt would read
G4 state truth   : state transitions read straight from sqlite rows
G5 accessibility : contrast-token palette, keyboard nav, visible focus (CSS from
                   design-system/kodand-memory/MASTER.md)

Run:  kodand memory-surface --repo ~/work/.kodand/repo-main --port 8881
"""

from __future__ import annotations

import json
import os
import threading
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_HTML_PATH = Path(__file__).resolve().parent.parent / "docs" / "k5-memory-surface.html"


class MemoryService:
    """Store-binding logic; testable without HTTP."""

    def __init__(self, repo: str):
        from kodand.recall import create_recall_engine
        from kodand.store import get_store

        self.repo = repo
        self.store = get_store(repo)
        self.engine = create_recall_engine(repo)

    def ledger(self, q: str = "", max_rows: int = 200) -> dict:
        rows = []
        for state, label in (("active", "active"), ("superseded", "superseded")):
            entries = self.store.list_memories(state=state)
            for entry in entries:
                text = entry.get("content", "")
                if q and q.lower() not in text.lower():
                    continue
                rows.append({
                    "id": entry.get("id") or entry.get("key"),
                    "state": state,
                    "memory_type": (entry.get("memory_type") or "reference"),
                    "updated_at": entry.get("updated_at"),
                    "content": text[:600],
                    "superseded_by": entry.get("superseded_by"),
                })
                if len(rows) >= max_rows:
                    break
        chains = {r["id"]: self.store.list_memories_with_supersede_chain(r["id"]) for r in rows[:80]}
        return {"repo": self.repo, "rows": rows, "chains": {str(k): v for k, v in chains.items()}}

    def entities(self) -> dict:
        from kodand.statemap import entities as statemap_entities

        return {"entities": statemap_entities(self.store)}

    def state(self, entity: str, as_of: float | None = None) -> dict:
        from kodand.statemap import get_state
        return get_state(self.store, entity, as_of=as_of) or {"entity": entity, "current": None}

    def artifacts(self) -> dict:
        conn = self.store._get_conn()
        rows = [dict(r) for r in conn.execute(
            "SELECT id, uri, sha256, kind, size, n_chunks, created_at FROM artifacts ORDER BY id DESC LIMIT 50"
        ).fetchall()]
        conn.close()
        return {"artifacts": rows}

    def events(self, kind: str = None, limit: int = 60) -> dict:
        return {"events": self.store.get_events(kind=kind, limit=limit)}

    def assembly(self, query: str, prefix: str, max_blocks: int = 6) -> dict:
        from kodand.assemble import assemble_v2 as k4assemble_v2
        from kodand.statemap import turn_entities
        results = self.engine.recall(query=query, k=max_blocks * 3)
        rows = [{
            "sessionId": (e.get("locator") or "-").split("#")[0],
            "entryId": e.get("id"),
            "content": e.get("content", ""),
        } for e in results]
        state = Path(os.path.expanduser(f"~/.kodand/surface-assemble-{sha256(self.repo.encode()).hexdigest()[:10]}.json"))
        kill = os.environ.get("KODAND_BASELINE") == "1"
        ents = [] if kill else turn_entities(self.store, query, rows)
        out = k4assemble_v2(prefix, rows, query, entities=ents, store=self.store,
                            state_path=state, kill_switch=kill, max_blocks=max_blocks)
        return out

    def correct(self, content: str, replaces_id: int | None = None) -> dict:
        entry = self.store.correct(content=content, replaces_id=replaces_id, origin="user")
        return {"entry": entry, "event": "correction(provenance=user)"}

    def supersede(self, entry_id: int, reason: str) -> dict:
        ok = self.store.supersede(entry_id, reason=reason or "surface-action")
        if not ok:
            raise ValueError(f"entry {entry_id} not found or already superseded")
        return {"superseded": entry_id, "event": "superseded(surface-action)"}


def make_handler(service: MemoryService):
    prefix_html = ("<p>You are the k5 memory surface demo agent. Repo conventions live here; "
                   "answers must cite memory ids.</p>")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence request logs
            pass

        def _json(self, obj, status=200):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _html(self, text):
            body = text.encode()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            n = int(self.headers.get("content-length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/" and _HTML_PATH.exists():
                return self._html(_HTML_PATH.read_text(encoding="utf-8"))
            if u.path == "/api/ledger":
                return self._json(self.service.ledger(q.get("q", [""])[0]))
            if u.path == "/api/entities":
                return self._json(self.service.entities())
            if u.path == "/api/state":
                return self._json(self.service.state(
                    q.get("entity", [""])[0],
                    float(q["as_of"][0]) if "as_of" in q else None))
            if u.path == "/api/artifacts":
                return self._json(self.service.artifacts())
            if u.path == "/api/events":
                return self._json(self.service.events(q.get("kind", [None])[0]))
            if u.path == "/api/assembly":
                return self._json(self.service.assembly(
                    q.get("q", ["What conventions apply?"])[0], prefix_html))
            return self._json({"error": f"no route {u.path}"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            body = self._body()
            if u.path == "/api/correct":
                content = (body.get("content") or "").strip()
                if not content:
                    return self._json({"error": "content required"}, 400)
                try:
                    replaces = int(body["replaces_id"]) if body.get("replaces_id") else None
                    return self._json(self.service.correct(content, replaces))
                except ValueError as e:
                    return self._json({"error": str(e)}, 400)
            if u.path == "/api/supersede":
                try:
                    return self._json(self.service.supersede(int(body["entry_id"]),
                                                             reason=body.get("reason", "")))
                except (ValueError, KeyError) as e:
                    return self._json({"error": str(e)}, 400)
            return self._json({"error": f"no route {u.path}"}, 404)

    Handler.service = service
    return Handler


def serve(repo: str, port: int = 8881, host: str = "127.0.0.1") -> tuple:
    svc = MemoryService(repo)
    server = ThreadingHTTPServer((host, port), make_handler(svc))
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, svc, f"http://{host}:{port}/"
