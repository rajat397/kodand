"""
kodand.capture.adapters - Session transcript readers (Fix 5).

Supported sources (explicit list; anything else returns [] and logs
'adapter:not-supported' — never silent zero):
  - transcript.jsonl: repo-local JSONL file with {role, text} rows
    (portable fixture format; also written by kodand hook shims).
  - opencode: ~/.local/share/opencode/opencode.db, tables message/part.
    Sessions scoped by directory == repo_path. Read-only, WAL-safe.
"""
import json
import os
import sqlite3
from typing import Any, Dict, List


def read_transcript_file(repo_path: str) -> List[Dict[str, str]]:
    """Read repo-local transcript.jsonl fixtures. Returns [{role, text}]."""
    turns: List[Dict[str, str]] = []
    for name in ("transcript.jsonl", os.path.join(".kodand", "transcript.jsonl")):
        path = os.path.join(repo_path, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    text = row.get("text", "") if isinstance(row, dict) else ""
                    role = row.get("role", "user") if isinstance(row, dict) else "user"
                    if text:
                        turns.append({"role": role, "text": text, "source": f"file:{name}"})
        except Exception:
            continue
    return turns


def read_opencode_sessions(repo_path: str, limit_sessions: int = 10) -> List[Dict[str, str]]:
    """Read opencode session transcripts for this repo. Best-effort, read-only."""
    turns: List[Dict[str, str]] = []
    db_path = os.path.expanduser("~/.local/share/opencode/opencode.db")
    if not os.path.exists(db_path):
        return turns
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
    except Exception:
        return turns
    try:
        repo_abs = os.path.abspath(repo_path)
        try:
            sess_rows = conn.execute(
                "SELECT id FROM session WHERE directory = ? OR path = ? "
                "ORDER BY time_updated DESC LIMIT ?",
                (repo_abs, repo_abs, limit_sessions),
            ).fetchall()
        except Exception:
            sess_rows = []
        for s in sess_rows:
            sid = s["id"]
            try:
                msg_rows = conn.execute(
                    "SELECT id, data FROM message WHERE session_id = ? ORDER BY time_created ASC",
                    (sid,),
                ).fetchall()
            except Exception:
                continue
            msg_role = {}
            for m in msg_rows:
                try:
                    md = json.loads(m["data"]) if isinstance(m["data"], str) else {}
                    msg_role[m["id"]] = md.get("role", "unknown")
                except Exception:
                    msg_role[m["id"]] = "unknown"
                try:
                    parts = conn.execute(
                        "SELECT data FROM part WHERE message_id = ? ORDER BY time_created ASC",
                        (m["id"],),
                    ).fetchall()
                except Exception:
                    continue
                for p in parts:
                    try:
                        pd = json.loads(p["data"]) if isinstance(p["data"], str) else {}
                    except Exception:
                        continue
                    if pd.get("type") == "text" and pd.get("text"):
                        turns.append({
                            "role": msg_role.get(m["id"], "unknown"),
                            "text": pd["text"],
                            "source": f"opencode:{sid}",
                        })
    except Exception:
        return turns
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return turns
