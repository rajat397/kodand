"""Fetch the laya decision-model checkpoint for `kodand rerank` consumers.

Downloads the multilingual checkpoint from Hugging Face (public, no token) into
`~/.kodand/models/laya-multilingual` and verifies SHA256 against the recorded
hash so a corrupted/partial download can never pass silently.

Usage: kodand fetch-model [--dest DIR]
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

BASE_URL = "https://huggingface.co/convaiinnovations/laya/resolve/main/multilingual"

# files that make a loadable checkpoint (matches the verified local layout)
FILES = [
    ("model.safetensors", "model.safetensors"),
    ("rl_agent_config.json", "rl_agent_config.json"),
    ("tokenizer/tokenizer.json", "tokenizer/tokenizer.json"),
    ("tokenizer/tokenizer_config.json", "tokenizer/tokenizer_config.json"),
    ("encoder/config.json", "encoder/config.json"),
]

MODEL_SHA256 = {
    "model.safetensors": "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204"
}


def default_dest() -> Path:
    return Path.home() / ".kodand" / "models" / "laya-multilingual"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "kodand-fetch-model/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total and os.environ.get("KODAND_QUIET") != "1":
                print(f"\r  {dest.name}: {got / 1e6:.1f} / {total / 1e6:.1f} MB",
                      end="", flush=True)
    if os.environ.get("KODAND_QUIET") != "1":
        print()


def fetch(dest: Path | None = None) -> dict:
    """Read-only safe: writes ONLY under dest. Returns a status dict."""
    dest = dest or default_dest()
    done = {}
    for src, rel in FILES:
        target = dest / rel
        need = MODEL_SHA256.get(rel)
        if target.exists() and (need is None or _sha256(target) == need):
            done[rel] = "cached"
            if os.environ.get("KODAND_QUIET") != "1":
                print(f"  {rel}: cached (verified)" if rel in MODEL_SHA256
                      else f"  {rel}: cached")
            continue
        _download(f"{BASE_URL}/{src}", target)
        if rel in MODEL_SHA256:
            got = _sha256(target)
            if got != MODEL_SHA256[rel]:
                target.unlink()
                raise RuntimeError(
                    f"sha256 mismatch for {rel}: expected {MODEL_SHA256[rel]}, got {got}"
                )
            done[rel] = "verified"
        else:
            done[rel] = "downloaded"
    config = dest / "rl_agent_config.json"
    config_ok = config.exists() and bool(json.loads(config.read_text()))
    if not config_ok:
        raise RuntimeError("checkpoint incomplete (rl_agent_config.json missing/invalid)")
    return {"dest": str(dest), "files": done, "ok": True}
