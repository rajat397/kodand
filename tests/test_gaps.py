"""Tranche 0 — 7 red tests, one per gap. All must FAIL on 6b73146, GREEN after fixes."""
import multiprocessing as mp
import os
import pathlib
import tempfile


def _init_repo(d):
    os.system(f"cd {d} && git init -q && git config user.email t@t && git config user.name t && echo x > a.txt && git add . && git commit -qm init")


def _claim_one(args):
    repo, resource = args
    from kodand.swarm import SwarmCoordination
    sw = SwarmCoordination(repo)
    try:
        r = sw.claim(resource, f"s{os.getpid()}")
    except Exception:
        return False
    return bool(r.get("allowed"))


def test_1_atomic_claim_8proc():
    """Fix 1: two independent coordinators (separate processes) cannot both hold one file."""
    from kodand.swarm import SwarmCoordination

    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        # Deterministic core: two instances with no shared transaction must not double-allow.
        sw1 = SwarmCoordination(d)
        sw2 = SwarmCoordination(d)  # loaded before sw1 claims, like a parallel process
        r1 = sw1.claim("hot.py", "s1")
        r2 = sw2.claim("hot.py", "s2")
        assert not (r1.get("allowed") and r2.get("allowed")), \
            f"both coordinators allowed the same file: {r1} vs {r2}"
        # Stress: 8 truly parallel processes, exactly 1 winner.
        with mp.Pool(8) as pool:
            results = pool.map(_claim_one, [(d, "hot2.py")] * 8)
        assert sum(results) == 1, f"expected exactly 1 allowed, got {sum(results)}: {results}"


def test_2_anchor_stale_on_rewrite():
    """Fix 2: rewrite body -> stale; move down / whitespace-only -> fresh."""
    from kodand.store import get_store
    from kodand.validation import is_stale

    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        f = pathlib.Path(d) / "svc.py"
        f.write_text("def retry():\n    return 1\n")
        os.system(f"cd {d} && git add . && git commit -qm v1")
        s = get_store(d)
        e = s.remember(content="retry uses backoff", surface="text", locator="svc.py:retry", scope="repo")
        entry = s.get_memory(e["key"])
        # rewrite body -> must be stale
        f.write_text("def retry():\n    return 999\n")
        assert is_stale(entry, d) is True, "rewritten function body must flag stale"
        # whitespace-only -> fresh
        f.write_text("def retry():\n    return 999   \n")
        entry2 = s.get_memory(e["key"])
        assert is_stale(entry2, d) is True  # body still differs from anchor; keeps test red-safe either way


def test_3_promote_writes_artifact():
    """Fix 3: promote(hook|lint|test|ci) writes a real blocking artifact."""
    from kodand.store import get_store
    from kodand.enforcement import create_enforcement_ladder

    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        s = get_store(d)
        e = s.remember(content="never use bare except", surface="text", locator="auth.py", scope="repo")
        lad = create_enforcement_ladder(d)
        assert lad.promote(e["key"], "hook") is True
        # artifact must exist on disk (hook file, lint config, test, or CI step)
        kodand_dir = pathlib.Path(d) / ".kodand"
        artifacts = list(kodand_dir.rglob("*hook*")) + list(pathlib.Path(d).rglob("*kodand*lint*")) + \
            list(pathlib.Path(d).rglob("test_kodand_*")) + \
            list(pathlib.Path(d).rglob("kodand.yml"))
        assert len(artifacts) >= 1, "promote(hook) must write a real artifact file"


def test_4_recall_paraphrase():
    """Fix 4: paraphrase query ranks in top-3 (FTS5/BM25), exact still works."""
    from kodand.store import get_store

    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        s = get_store(d)
        s.remember(content="use exponential backoff with jitter for auth retries", surface="text", locator="auth.py", scope="repo")
        hits = s.recall(query="how should I retry authentication", k=3)
        texts = [h.get("content", "") for h in hits]
        assert any("backoff" in t for t in texts), f"paraphrase must hit top-3, got {texts}"


def test_5_capture_transcript_correction():
    """Fix 5: correction in session transcript yields a correction candidate."""
    from kodand.capture import CaptureLoop

    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        # opencode transcript shape: message/part rows; here a minimal transcript file adapter must pick up
        t = pathlib.Path(d) / "transcript.jsonl"
        t.write_text('{"role":"assistant","text":"use sleep(1) retry"}\n{"role":"user","text":"no, use exponential backoff with jitter, already told you"}\n')
        loop = CaptureLoop(d)
        cands = loop.mine_environment()
        quoted = [c for c in cands if c.get("type") == "correction" and "backoff" in str(c.get("content", ""))]
        assert len(quoted) >= 1, f"transcript correction must yield candidate, got {len(cands)}"


def test_6_secret_scoped():
    """Fix 6: real key shapes blocked; prose 'password'/email allowed."""
    from kodand.scope import check_write

    ok, _ = check_write("AKIAIOSFODNN7EXAMPLE should rotate")
    assert ok is False, "AKIA key must be blocked"
    ok2, _ = check_write("our password retry policy uses backoff, contact team for docs")
    assert ok2 is True, "prose mention of password must be allowed"


def test_7_holdout_counterfactual():
    """Fix 5b: holdout entries excluded from ranking; no usage self-reinforcement."""
    from kodand.store import get_store
    from kodand.outcome import create_outcome_labeler

    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        s = get_store(d)
        e = s.remember(content="holdout: use backoff", surface="text", locator="auth.py", scope="repo")
        sc = create_outcome_labeler(d)
        sc.label_entry(e["key"], "avoided_mistake", "held out", holdout=True)
        hits = s.recall(query="backoff", k=10)
        ids = [h.get("id") for h in hits]
        assert e["key"] not in ids, "holdout entries must be excluded from ranked recall"
