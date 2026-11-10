"""Persistent recall server: removes the ~16s python spawn per kodand recall call.

Protocol (one line per request, one line per reply):
  {"repo": str, "query": str, "k": int}
  {"rows": [...], "error": null|str}

Repos are cached with a small LRU (sqlite handles stay open; no model loaded).
"""

from __future__ import annotations

import json
import os
import sys
import threading
from collections import OrderedDict

DEFAULT_PORT = 8766


def _recall(repo: str, query: str, k: int, cache: OrderedDict, cachelock: threading.Lock):
    with cachelock:
        engine = cache.get(repo)
        if engine is None:
            from kodand.recall import create_recall_engine

            engine = create_recall_engine(repo)
            cache[repo] = engine
            while len(cache) > 6:
                cache.popitem(last=False)
    return engine.recall(query=query or "", k=k)


def serve_tcp(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
    import socketserver

    # thread placement: LRU cache is shared under cachelock; repos hash O(1)

    cache: OrderedDict = OrderedDict()
    cachelock = threading.Lock()

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            for line in self.rfile:
                line = line.strip()
                if not line:
                    continue
                try:
                    req = json.loads(line)
                    rows = _recall(str(req["repo"]), str(req.get("query") or ""), int(req.get("k", 10)), cache, cachelock)
                    out = [
                        {"id": e.get("id"), "content": e.get("content", ""),
                         "locator": e.get("locator", ""), "scope": e.get("scope", "repo")}
                        for e in rows
                    ]
                    reply = {"rows": out, "error": None}
                except Exception as e:  # noqa: BLE001 - answer bad requests, keep server alive
                    reply = {"rows": [], "error": f"{type(e).__name__}: {e}"}
                self.wfile.write((json.dumps(reply) + "\n").encode())
                self.wfile.flush()

    server = socketserver.ThreadingTCPServer((host, port), Handler)
    server.daemon_threads = True
    print(f"kodand recalld listening on {server.server_address}", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    serve_tcp(os.environ.get("KODAND_RECALL_HOST", "127.0.0.1"))
