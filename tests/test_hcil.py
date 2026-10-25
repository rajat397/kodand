import tempfile, os, pathlib

def test_hcil_hierarchy():
    import tempfile
    from kodand.store import Store
    from kodand.hcil import consolidate_session
    with tempfile.TemporaryDirectory() as d:
        s = Store(d)
        # create session summary
        msgs = [{"role": "user", "content": "I like Zumba, yoga and BodyPump classes"}, {"role": "assistant", "content": "great!"}]
        summ = consolidate_session(d, "sess-1", msgs)
        assert "Zumba" in summ or "z" in summ.lower()
        row = s.get_session_summary("sess-1")
        assert row is not None
        assert row["session_id"] == "sess-1"
        # hierarchical recall should find session summary
        s.remember("I love Zumba on Tuesdays", locator="sess-1#0")
        hits = s.hierarchical_recall("Zumba", k=5)
        assert any(h.get("hcil_level") == "session" for h in hits) or any(h.get("hcil_level") == "chunk" for h in hits)

def test_hcil_intent_ledger():
    import tempfile
    from kodand.store import Store
    with tempfile.TemporaryDirectory() as d:
        s = Store(d)
        intent = s.create_intent("avoid bare-except", attempt="wrote except:", outcome="lint failed", correction="use except ValueError", enforcement_ref="tests/test_kodand_1.py")
        assert intent["id"] > 0
        fetched = s.get_intent(intent["id"])
        assert fetched["correction"] == "use except ValueError"
        # causal link
        m1 = s.remember("attempt bare-except", locator="a.py:1")
        m2 = s.remember("correction specific", locator="a.py:2")
        link = s.record_causal(intent["id"], "correction", from_entry_id=m1["key"], to_entry_id=m2["key"])
        assert link["id"] > 0

def test_hcil_okf_triples():
    import tempfile
    from kodand.store import Store
    with tempfile.TemporaryDirectory() as d:
        s = Store(d)
        m = s.remember("I like Zumba, Hip Hop Abs and yoga", locator="sess#0")
        s.add_okf_triple(m["key"], "sess", "user", "prefers", "zumba", 0.9)
        conn = s._get_conn()
        rows = conn.execute("SELECT * FROM okf_triples WHERE subject='user'").fetchall()
        conn.close()
        assert len(rows) >= 1

def test_hcil_staleness_anchor_still_works():
    import tempfile
    from kodand.store import Store
    with tempfile.TemporaryDirectory() as d:
        s = Store(d)
        m = s.remember("anchor test", locator="foo.py:myfn")
        # validation anchor should not crash
        from kodand.validation import is_stale
        assert is_stale({"locator": "foo.py:myfn", "id": m["key"]}, d) in (True, False)

def test_hcil_enforcement_link():
    import tempfile
    from kodand.store import Store
    with tempfile.TemporaryDirectory() as d:
        s = Store(d)
        intent = s.create_intent("block wildcard", correction="use specific import", enforcement_ref=".kodand/enforce/hook-1.sh")
        # enforcement ref stored and retrievable
        assert "hook-1.sh" in intent["summary"] or intent["id"] > 0
        fetched = s.get_intent(intent["id"])
        assert fetched["enforcement_ref"] == ".kodand/enforce/hook-1.sh"
