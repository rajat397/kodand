"""Laya-backed retrieval filter.

Scores each candidate chunk with a non-generative decision model (Laya) and
keeps the top-k sessions by P(the chunk would help answer the question).

The absolute probability is not comparable across questions, so the rule is
relative: rank within the question, then dedupe to sessions. Measured on the
20-question adv30-hybrid-fixed set: session evidence recall@10 0.520 -> 0.718
with 8 kept sessions (one chunk each).

`serve()` runs a long-lived JSONL loop so callers do not pay the ~28 s model
load on every query.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
from collections import OrderedDict
from collections.abc import Iterable
from typing import Any

DEFAULT_MODEL = os.environ.get("KODAND_LAYA_MODEL", "/mnt/data/models/laya-multilingual")
DEFAULT_URL = os.environ.get("KODAND_LAYA_URL", "")
INSTRUCTION = "This passage would help answer the question: {q}"
BATCH_SIZE = 8
DEFAULT_PORT = 8765
# 400 chars halves encoder cost per chunk with no quality change vs 800 on the
# 20-question A/B (any 16/20, all 11/20, session recall 0.718 == 800-char).
DEFAULT_MAX_CHARS = int(os.environ.get("KODAND_LAYA_MAX_CHARS", "400"))


def _load(model_path: str):
    try:
        import laya
    except ImportError as e:
        raise RuntimeError(
            "laya is not installed; run `pip install laya` to enable the retrieval filter"
        ) from e
    if not os.path.isdir(model_path):
        raise RuntimeError(f"Laya checkpoint not found: {model_path}")
    return laya.load(model_path, device="cpu")


def _questions(query: str) -> dict[str, dict[str, Any]]:
    return {"c": {"type": "noul", "instructions": INSTRUCTION.format(q=query)}}


# Session timestamps: prefer dates written inside the chunk content (benchmark
# chunks carry "[session-N 10:20 am on 20 May, 2023]"; real sessions may too);
# created_at is the fallback (bulk ingests stamp all rows at import time, so it
# only separates sessions when chunks arrived over time).
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_DATE_RE = re.compile(
    r"(\d{1,2}):(\d{2})\s*(?:am|pm)?\s*on\s*(\d{1,2})\s+([A-Za-z]{3,})[,\s]+(\d{4})"
    r"|\b(\d{4})-(\d{2})-(\d{2})\b")


def session_timestamp(group: list[dict[str, Any]]) -> float:
    """Newest parseable timestamp among a session's chunks; 0.0 when unknown."""
    import datetime as _dt

    best = 0.0
    for chunk in group:
        cand = float(chunk.get("created_at") or 0)
        content = str(chunk.get("content", ""))[:600]
        m = _DATE_RE.search(content)
        if m:
            try:
                if m.group(4):
                    hh, mm, day, mon, year = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4).lower()[:3], int(m.group(5))
                    month = _MONTHS.get(mon)
                    if month:
                        if m.group(2) == "pm" and hh < 12:
                            hh += 12
                        cand = _dt.datetime(year, month, day, min(hh, 23), min(mm, 59)).timestamp()  # noqa: DTZ001 (bench dates are naive; only relative order matters)
                elif m.group(6):
                    cand = _dt.datetime(int(m.group(6)), int(m.group(7)), int(m.group(8))).timestamp()  # noqa: DTZ001
            except (ValueError, OverflowError):
                pass
        best = max(best, cand)
    return best


def score_chunks(
    query: str,
    chunks: Iterable[dict[str, Any]],
    *,
    model_path: str | None = None,
    max_chars: int | None = None,
    max_len: int = 1024,
    agent=None,
) -> list[dict[str, Any]]:
    """Return each chunk with a `laya_p` field, preserving input order."""
    rows = [dict(c) for c in chunks]
    if not rows:
        return []
    max_chars = DEFAULT_MAX_CHARS if max_chars is None else max_chars
    agent = agent or _load(model_path or DEFAULT_MODEL)
    questions = _questions(query)
    states = [
        "Passage: " + " ".join(str(row.get("content", "")).split())[:max_chars] for row in rows
    ]
    batch = getattr(agent, "predict_batch", None)
    if batch is not None:
        results = batch(states, questions, batch_size=BATCH_SIZE, max_len=max_len)
    else:
        results = [agent.predict(s, questions, max_len=max_len) for s in states]
    for row, result in zip(rows, results):
        row["laya_p"] = float(result["answers"]["c"]["noul"])
    return rows


def filter_sessions(
    query: str,
    chunks: Iterable[dict[str, Any]],
    *,
    keep_sessions: int = 8,
    model_path: str | None = None,
    max_chars: int | None = None,
    max_len: int = 1024,
    agent=None,
) -> list[dict[str, Any]]:
    """Rank chunks by P(help), keep the best chunk from each of the top-k sessions."""
    scored = score_chunks(
        query, chunks, model_path=model_path, max_chars=max_chars, max_len=max_len, agent=agent
    )
    if not scored:
        return []
    best: dict[str, dict[str, Any]] = {}
    for row in scored:
        session = str(row.get("locator", "")).split("#")[0] or str(row.get("id", ""))
        prev = best.get(session)
        if prev is None or row["laya_p"] > prev["laya_p"]:
            best[session] = row
    ordered = sorted(best.values(), key=lambda r: -r["laya_p"])[: max(1, keep_sessions)]
    return ordered


def score_sessions(
    query: str,
    chunks: Iterable[dict[str, Any]],
    *,
    model_path: str | None = None,
    max_chars: int | None = None,
    max_len: int = 1024,
    session_chars: int = 700,
    recency: bool = False,
    agent=None) -> list[dict[str, Any]]:
    """Judge whole sessions (not chunks): one text per session keeps its chunks.

    Session text = BM25-best chunks of that session joined, capped at
    `session_chars`. Returns per-session rows: {"session", "laya_p", "chunks"}.
    With `recency`, each row also carries `session_ts` (epoch seconds; the
    newest usable timestamp among the session's chunks), which rank_sessions
    uses to break near-ties.
    """
    max_chars = DEFAULT_MAX_CHARS if max_chars is None else max_chars
    chunks = [dict(c) for c in chunks]
    if not chunks:
        return []
    by_session: OrderedDict = OrderedDict()
    for chunk in chunks:
        session = str(chunk.get("locator", "")).split("#")[0] or str(chunk.get("id", ""))
        by_session.setdefault(session, []).append(chunk)
    agent = agent or _load(model_path or DEFAULT_MODEL)
    questions = {"c": {"type": "noul",
                       "instructions": INSTRUCTION.format(q=query),
                      }}
    if questions["c"]["instructions"].startswith(INSTRUCTION.split("{")[0]):
        questions["c"]["instructions"] = "This session would help answer the question: " + query
    rows = []
    for session, group in by_session.items():
        parts = []
        for chunk in group[:3]:
            text = " ".join(str(chunk.get("content", "")).split())[: max_chars]
            if text:
                parts.append(text)
            if sum(len(p) for p in parts) >= session_chars:
                break
        text = "...".join(parts)[: session_chars]
        # virtual row keeps the session's chunks intact for downstream ranking
        row = dict(group[0])
        row["locator"] = f"{session}#session"
        row["session_chunks"] = group
        row["session_text"] = text
        if recency:
            row["session_ts"] = session_timestamp(group)
        rows.append(row)
    results = []
    batch = getattr(agent, "predict_batch", None)
    texts = ["Passage: " + r["session_text"] for r in rows]
    if batch is not None:
        scored = batch(texts, questions, batch_size=BATCH_SIZE, max_len=max_len)
    else:
        scored = [agent.predict(t, questions, max_len=max_len) for t in texts]
    for row, res in zip(rows, scored):
        row["laya_p"] = float(res["answers"]["c"]["noul"])
        results.append(row)
    return results


def rank_sessions(
    query: str,
    chunks: Iterable[dict[str, Any]],
    *,
    keep_chunks: int = 10,
    session_budget: int = 10,
    recency_band: float = 0.0,
    agent=None,
    **kw,
) -> list[dict[str, Any]]:
    """Rank sessions by relevance; return up to `keep_chunks` chunks total.

    Sessions ordered by laya P (desc); a session contributes ALL of its chunks
    (BM25 order) so the answer model keeps the multi-chunk context it needs.
    Ties and very low scores do not drop chunks: cuts happen by chunk budget.

    `recency_band` (from milestone M3, off by default): when two sessions'
    relevance differs by less than the band, the newer session ranks first.
    0.0 disables; the default band in production is 0.10 (env KODAND_LAYA_RECENCY).
    """
    judged = score_sessions(query, chunks, agent=agent, **kw)
    if not judged:
        return []
    if recency_band > 0 and any(r.get("session_ts", 0) for r in judged):
        # Stable sort keeps laya order inside bands; newer-first across bands.
        judged.sort(key=lambda r: r.get("session_ts", 0), reverse=True)
        groups = []
        for row in judged:
            placed = False
            for g in groups:
                if abs(g[0]["laya_p"] - row["laya_p"]) <= recency_band:
                    g.append(row)
                    g.sort(key=lambda r: -r["laya_p"])
                    placed = True
                    break
            if not placed:
                groups.append([row])
        judged2 = [r for g in sorted(groups, key=lambda g: -g[0]["laya_p"]) for r in g]
    else:
        judged2 = sorted(judged, key=lambda r: -r["laya_p"])
    judged2 = judged2[:session_budget]
    out = []
    for row in judged2:
        for chunk in row["session_chunks"]:
            if len(out) >= keep_chunks:
                break
            item = dict(chunk)
            item["session_p"] = row["laya_p"]
            if row.get("session_ts"):
                item["session_ts"] = row["session_ts"]
            out.append(item)
        if len(out) >= keep_chunks:
            break
    return out


def hybrid_rank(
    query: str,
    chunks: Iterable[dict[str, Any]],
    *,
    keep_chunks: int = 10,
    seed_slots: int = 6,
    fill_slots: int = 4,
    recency_band: float = 0.0,
    agent=None,
    **kw,
) -> list[dict[str, Any]]:
    """Option-C hybrid rank: BM25 seeds + laya fills, chunk budget unchanged.

    Seed slots take the session-best chunk of the first `seed_slots` DISTINCT
    sessions in BM25 (input) order. Fill slots add the next-best session (by
    laya P, recency-band aware) whose best chunk sits outside the seeded
    sessions. Output is capped at `keep_chunks` chunks overall. Sessions keep
    ALL their chunks when the budget allows, preserving multi-chunk evidence.
    """
    judged = score_sessions(
        query, chunks, agent=agent, recency=recency_band > 0, model_path=kw.get("model_path")
    )
    if not judged:
        return []
    by_first = OrderedDict()
    for row in judged:
        ses = row["locator"].split("#")[0]
        if ses not in by_first:
            by_first[ses] = row
    seeds = list(by_first)[: max(1, seed_slots)]
    seed_set = set(seeds)
    rest = [r for r in judged if r["locator"].split("#")[0] not in seed_set]
    if recency_band > 0:
        for r in rest:
            r.setdefault("session_ts", 0.0)
        # newest-first inside laya-tie bands among the fillers
        rest.sort(key=lambda r: r.get("session_ts", 0), reverse=True)
        banded = []
        for r in rest:
            placed = False
            for g in banded:
                if abs(g[0]["laya_p"] - r["laya_p"]) <= recency_band:
                    g.append(r)
                    g.sort(key=lambda x: -x["laya_p"])
                    placed = True
                    break
            if not placed:
                banded.append([r])
        rest = [r for g in sorted(banded, key=lambda g: -g[0]["laya_p"]) for r in g]
    else:
        rest.sort(key=lambda r: -r["laya_p"])
    fill = rest[: max(1, fill_slots)]
    out = []
    seen_budget = 0
    for order in [by_first[s] for s in seeds] + fill:
        if len(out) >= keep_chunks:
            break
        for chunk in order["session_chunks"]:
            if len(out) >= keep_chunks:
                break
            item = dict(chunk)
            item["session_p"] = order["laya_p"]
            if order.get("session_ts"):
                item["session_ts"] = order["session_ts"]
            out.append(item)
            seen_budget += 1
    return out


def serve(model_path: str | None = None, out=None) -> None:
    """JSONL request/response loop: one model load, many queries.

    Request:  {"id": any, "query": str, "chunks": [...], "keep": int}
    Response: {"id": any, "kept": [...], "error": null|str}
    """
    real_out = out or sys.stdout
    # Laya and torch may print to stdout; keep the protocol stream clean.
    sys.stdout = sys.stderr
    agent = None
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            req: dict[str, Any] = {}
            try:
                req = json.loads(line)
                if agent is None:
                    agent = _load(model_path or DEFAULT_MODEL)
                kept = filter_sessions(
                    req["query"],
                    req.get("chunks") or [],
                    keep_sessions=int(req.get("keep", 8)),
                    agent=agent,
                )
                reply = {"id": req.get("id"), "kept": kept, "error": None}
            except Exception as e:  # noqa: BLE001 - answer bad requests, keep loop alive
                reply = {"id": req.get("id"), "kept": [], "error": f"{type(e).__name__}: {e}"}
            real_out.write(json.dumps(reply) + "\n")
            real_out.flush()
    finally:
        sys.stdout = real_out


def build_tcp_server(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    *,
    model_path: str | None = None,
    agent=None,
):
    """Build the TCP JSONL server; the model loads once before serving.

    One request per line: {"query": str, "chunks": [...], "keep": int}
    One response per line: {"kept": [...], "error": null|str}
    """
    import socketserver

    agent = agent or _load(model_path or DEFAULT_MODEL)

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            for line in self.rfile:
                line = line.strip()
                if not line:
                    continue
                try:
                    req = json.loads(line)
                    if req.get("mode", "sessions") == "hybrid":
                        kept = hybrid_rank(
                            req["query"],
                            req.get("chunks") or [],
                            keep_chunks=int(req.get("keep_chunks", 10)),
                            seed_slots=int(req.get("seed_slots", 6)),
                            fill_slots=int(req.get("fill_slots", 4)),
                            recency=bool(os.environ.get("KODAND_LAYA_RECENCY")),
                            agent=agent,
                        )
                    elif req.get("mode", "sessions") == "sessions":
                        recency_band = float(req.get("recency_band", 0.0))
                        if os.environ.get("KODAND_LAYA_RECENCY"):
                            recency_band = recency_band or 0.10
                        kept = rank_sessions(
                            req["query"],
                            req.get("chunks") or [],
                            keep_chunks=int(req.get("keep_chunks", 10)),
                            recency_band=recency_band,
                            recency=recency_band > 0,
                            agent=agent,
                        )
                    else:
                        kept = filter_sessions(
                            req["query"],
                            req.get("chunks") or [],
                            keep_sessions=int(req.get("keep", 8)),
                            agent=agent,
                        )
                    reply = {"kept": kept, "error": None}
                except Exception as e:  # noqa: BLE001 - answer bad requests, keep server alive
                    reply = {"kept": [], "error": f"{type(e).__name__}: {e}"}
                self.wfile.write((json.dumps(reply) + "\n").encode())
                self.wfile.flush()

    server = socketserver.ThreadingTCPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def serve_tcp(
    host: str = "127.0.0.1", port: int = DEFAULT_PORT, model_path: str | None = None
) -> None:
    server = build_tcp_server(host, port, model_path=model_path)
    print(f"kodand rerank-serve listening on {server.server_address}", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _parse_url(url: str) -> tuple[str, int]:
    host, _, port = url.partition(":")
    return host or "127.0.0.1", int(port or DEFAULT_PORT)


def filter_via_socket(
    query: str,
    chunks: Iterable[dict[str, Any]],
    *,
    url: str | None = None,
    keep_sessions: int = 8,
    keep_chunks: int = 10,
    mode: str = "sessions",
    timeout: float = 300.0,
) -> list[dict[str, Any]]:
    """Send one request to a running `kodand rerank-serve` and return kept chunks."""
    host, port = _parse_url(url or DEFAULT_URL)
    payload = json.dumps({"query": query, "chunks": list(chunks), "keep": keep_sessions,
                          "keep_chunks": keep_chunks, "mode": mode}) + "\n"
    try:
        with socket.create_connection((host, port), timeout=5.0) as sock:
            sock.settimeout(timeout)
            sock.sendall(payload.encode())
            reader = _readline(sock)
            reply = json.loads(reader)
    except (TimeoutError, ConnectionRefusedError, OSError) as e:
        raise RuntimeError(
            f"no rerank server on {host}:{port} ({type(e).__name__}: {e}); start one with `kodand rerank-serve`"
        ) from e
    if reply.get("error"):
        raise RuntimeError(f"rerank server error: {reply['error']}")
    return reply.get("kept") or []


def _readline(sock) -> str:
    buf = bytearray()
    while True:
        part = sock.recv(4096)
        if not part:
            break
        buf += part
        if b"\n" in buf:
            break
    return bytes(buf).decode().strip()
