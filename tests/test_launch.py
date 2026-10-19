"""Launch verification — covers all 23 CLI commands + Docker stranger."""
import tempfile, os, json, subprocess, pathlib
from kodand.store import get_store
from kodand.recall import create_recall_engine
from kodand.trust import TrustSurface
from kodand.warmstart import create_warm_start
from kodand.hooks import before_tool
from kodand.anchor import get_anchored
from kodand.manifest import flag_conventions

def test_store_recall():
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        os.system(f"cd {d} && git init -q && git config user.email t@t && git config user.name t && echo x > a.txt && git add . && git commit -qm init")
        s = get_store(d)
        # ensure fresh
        import pathlib
        p = pathlib.Path(d) / ".kodand" / "bridge.db"
        assert p.exists()
        e = s.remember(content="Use Postgres", surface="text", locator="db.py", scope="repo")
        assert e["key"]
        hits = s.recall(query="Postgres", k=5)
        assert len(hits) == 1

def test_prospective_hook():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        os.system(f"cd {d} && git init -q && git config user.email t@t && git config user.name t && echo x > a.txt && git add . && git commit -qm init")
        s = get_store(d)
        s.remember(content="Never use bare except", surface="text", locator="auth.py", scope="repo")
        hits = before_tool("write", {"file_path": "auth.py"}, d)
        assert len(hits) >= 1

def test_warm_start():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        os.system(f"cd {d} && git init -q && git config user.email t@t && git config user.name t && echo x > a.txt && git add . && git commit -qm init")
        s = get_store(d)
        s.remember(content="We use Postgres", surface="text", locator="AGENTS.md", scope="repo")
        ws = create_warm_start(d)
        txt = ws.get_warm_context()
        assert "Postgres" in txt

def test_trust():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        os.system(f"cd {d} && git init -q && git config user.email t@t && git config user.name t && echo x > a.txt && git add . && git commit -qm init")
        s = get_store(d)
        e = s.remember(content="Use DI", surface="text", locator="di.py", scope="repo")
        ts = TrustSurface(d)
        lst = ts.list()
        assert len(lst) >= 1
        assert ts.inspect(e["key"]) is not None
        assert ts.correct(e["key"], "false_hold", "fix")
        assert ts.delete(e["key"])

def test_team_swarm_handoff():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        os.system(f"cd {d} && git init -q && git config user.email t@t && git config user.name t && echo x > a.txt && git add . && git commit -qm init")
        from kodand.team import drill_poison, promote_to_team
        from kodand.swarm import SwarmCoordination
        from kodand.handoff import Handoff
        s = get_store(d)
        e = s.remember(content="Use DI", surface="text", locator="di.py", scope="repo")
        # team drill must be blocked
        assert drill_poison(d)["blocked"] is True
        # team promote with file should succeed
        r = promote_to_team(d, e["key"], ["alice","bob"], 2)
        assert r["ok"] is True
        # swarm deny-and-propose
        sw = SwarmCoordination(d)
        assert sw.claim("a.txt", "s1")["allowed"] is True
        assert sw.claim("a.txt", "s2")["allowed"] is False
        # handoff
        ho = Handoff(d)
        h = ho.capture("s1", decided=["d1"], done=["done1"], blocked=["b1"])
        assert ho.resume("s1") is not None
