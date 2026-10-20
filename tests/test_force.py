"""Forcing function: after_write gate blocks enforced mistakes, allows clean writes."""
import os
import tempfile


def _init_repo(d):
    os.system(f"cd {d} && git init -q && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m init")


def test_force_blocks_enforced_mistake():
    from kodand.store import get_store
    from kodand.enforcement import create_enforcement_ladder
    from kodand.hooks import after_write

    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        s = get_store(d)
        e = s.remember(content="never use `from utils import *`, import names explicitly",
                       surface="text", locator="mod.py", scope="repo")
        assert create_enforcement_ladder(d).promote(e["key"], "test") is True
        bad = after_write("mod.py", "from utils import *\ngo()\n", d)
        assert bad["allowed"] is False, f"must block, got {bad}"
        assert bad["violations"] and bad["violations"][0]["id"] == e["key"]
        good = after_write("mod.py", "from utils import helper\ngo()\n", d)
        assert good["allowed"] is True, f"clean write must pass, got {good}"


def test_force_fail_open_without_enforcement():
    from kodand.hooks import after_write
    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        r = after_write("a.py", "anything at all", d)
        assert r["allowed"] is True
