"""
kodand.manifest - Manifest watch (C6.2, Iter 9)
Flag convention memories when a manifest diff changes a dependency they depend on.
"""
import os
import json
import hashlib
import subprocess
from typing import List, Dict, Set
from kodand.store import get_store

MANIFESTS = {
    "requirements.txt": "pip",
    "package.json": "npm",
    "Cargo.toml": "cargo",
    "go.mod": "go",
    "pyproject.toml": "pip",
    "Gemfile": "bundler",
    "pom.xml": "maven",
}

def discover_manifests(repo_path: str) -> List[str]:
    found = []
    for name in MANIFESTS:
        p = os.path.join(repo_path, name)
        if os.path.exists(p):
            found.append(p)
    # Also search one level deep for monorepo
    try:
        for root, dirs, files in os.walk(repo_path):
            if ".git" in dirs:
                dirs.remove(".git")
            if "__pycache__" in dirs:
                dirs.remove("__pycache__")
            depth = root[len(repo_path):].count(os.sep)
            if depth > 2:
                dirs[:] = []
                continue
            for f in files:
                if f in MANIFESTS:
                    full = os.path.join(root, f)
                    if full not in found:
                        found.append(full)
    except Exception:
        pass
    return found

def _parse_requirements(path: str) -> Set[str]:
    deps = set()
    try:
        with open(path) as f:
            for line in f:
                line=line.strip()
                if not line or line.startswith("#"):
                    continue
                # handle pkg==1.2.3, pkg>=1.0, pkg[extra]==1.0
                name = line.split("==")[0].split(">=")[0].split("~=")[0].split("[")[0].strip().lower()
                if name:
                    deps.add(name)
    except Exception:
        pass
    return deps

def _parse_package_json(path: str) -> Set[str]:
    try:
        with open(path) as f:
            j=json.load(f)
        deps=set()
        for k in ("dependencies","devDependencies","peerDependencies"):
            if k in j and isinstance(j[k], dict):
                for name in j[k].keys():
                    deps.add(name.lower())
        return deps
    except Exception:
        return set()

def parse_manifest(path: str) -> Set[str]:
    name = os.path.basename(path)
    if name == "requirements.txt":
        return _parse_requirements(path)
    if name == "package.json":
        return _parse_package_json(path)
    # generic: return empty for unsupported but still flag via file name
    return set()

def _file_hash(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]
    except Exception:
        return ""

def flag_conventions(repo_path: str) -> List[Dict]:
    """Flag convention memories whose dependency appears in a manifest diff.
    Compares current manifest hashes vs previous run (stored in .kodand/manifest_state.json).
    Returns list of flagged memories (with reason).
    """
    store = get_store(repo_path)
    state_path = os.path.join(repo_path, ".kodand", "manifest_state.json")
    manifests = discover_manifests(repo_path)
    # Build current state
    cur = {}
    for p in manifests:
        cur[p] = _file_hash(p)
    # Load previous
    prev = {}
    if os.path.exists(state_path):
        try:
            with open(state_path) as f:
                prev = json.load(f)
        except Exception:
            prev = {}
    # Find changed manifests
    changed = []
    for p, h in cur.items():
        if prev.get(p) != h:
            changed.append(p)
    # If no previous state, treat as no change (first run) - just save and return empty
    if not prev:
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w") as f:
                json.dump(cur, f)
        except Exception:
            pass
        return []
    # For each changed manifest, parse deps and find convention memories mentioning them
    flagged = []
    for p in changed:
        deps = parse_manifest(p)
        # Also consider file basename as dep signal if parse empty
        if not deps:
            deps = {os.path.basename(p).lower()}
        # Search convention memories
        for dep in deps:
            # Simple: recall memories containing dep name and type convention/decision
            hits = store.recall(query=dep, k=20)
            for h in hits:
                if h.get("memory_type", "reference") in ("convention", "decision") or "convention" in h.get("content","").lower():
                    flagged.append({
                        "memory_id": h["id"],
                        "content": h["content"][:120],
                        "manifest": os.path.relpath(p, repo_path),
                        "dependency": dep,
                        "reason": f"manifest {os.path.basename(p)} changed, convention mentions '{dep}'"
                    })
    # Save current state
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(cur, f)
    except Exception:
        pass
    return flagged
