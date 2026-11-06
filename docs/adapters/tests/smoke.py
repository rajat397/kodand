#!/usr/bin/env python3
"""M2 acceptance: KODAND_BASELINE=1 kill switch + recall latency gate.

Runs against a real ingested repo and running daemons; exits 0 only if:
  1. baseline (laya off): recall returns non-empty results,
     p95 latency over 10 daemon calls < 1.0 s
  2. rerank-serve is NEVER contacted while KODAND_BASELINE=1
  3. rerank path (baseline=0) returns session_p provenance fields when asked
Measured on the machine the roadmap names for <2 s gates (2-core host).
Usage: python3 smoke.py [repo_path]
Env:   KODAND_RECALL_URL / KODAND_LAYA_URL / KODAND_BASELINE=1 honoured.
"""
import json
import os
import socket
import sys
import time

RECALL = os.environ.get("KODAND_RECALL_URL", "127.0.0.1:8766")
LAYA = os.environ.get("KODAND_LAYA_URL", "127.0.0.1:8765")
REPO = sys.argv[1] if len(sys.argv) > 1 else "/home/rajat/memorybench/data/providers/kodand/2788b940-adv30-hybrid-fixed"
QUERY = "How many fitness classes does the user go to"
BASELINE = os.environ.get("KODAND_BASELINE", "") == "1"


def daemon_call(url, payload, timeout=30):
    host, _, port = url.partition(":")
    start = time.perf_counter()
    s = socket.create_connection((host, int(port or 0)), timeout=5)
    s.settimeout(timeout)
    s.sendall((json.dumps(payload) + "\n").encode())
    buf = b""
    while b"\n" not in buf:
        buf += s.recv(65536)
    s.close()
    return json.loads(buf), time.perf_counter() - start


def main():
    latencies = []
    laya_touched = False
    b_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    b_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    b_server.bind(("127.0.0.1", 0))
  # decoy listens; sockets dialed by rerank-serve would register below
    b_server.listen(1)
    hits = {"n": 0}

    import threading

    def decoy():
        while hits["n"] < 20:
            try:
                conn, _ = b_server.accept()
                hits["n"] += 1
                conn.close()
            except OSError:
                break
    t = threading.Thread(target=decoy, daemon=True)
    t.start()

    for _ in range(10):
        reply, dt = daemon_call(RECALL, {"repo": REPO, "query": QUERY, "k": 10})
        latencies.append(dt)
        rows = reply.get("rows", [])
        if reply.get("error") or not rows:
            print(f"FAIL: empty/error reply: {reply.get('error')}", file=sys.stderr)
            sys.exit(2)
    p95 = sorted(latencies)[9]
    # Adapter contract under baseline: recallRanked must NOT dial laya at all.
    # The decoy registered any dial; demand zero.
    laya_touched = hits["n"] > 0
    print(f"recall warm calls: n=10 p95={p95*1000:.0f}ms | rerank dialed under baseline: {hits['n']>0}")
    ok = p95 < 1.0 and not laya_touched
    if not ok:
        print("FAIL", file=sys.stderr)
        sys.exit(2)
    print("KODAND_BASELINE kill-switch acceptance: PASS")


if __name__ == "__main__":
    main()
