import pytest

from kodand.rerank import filter_sessions, rank_sessions, score_chunks


class FakeAgent:
    """Deterministic stand-in for a loaded Laya agent."""

    def __init__(self, table):
        self.table = table
        self.calls = []

    def predict(self, state, questions, max_len=1024):
        self.calls.append((state, questions, max_len))
        text = state.removeprefix("Passage: ")
        return {"answers": {"c": {"noul": self.table.get(text, 0.0)}}}


def chunk(cid, content, locator):
    return {"id": cid, "content": content, "locator": locator, "scope": "repo"}


def test_scores_use_passage_as_state_and_question_as_instruction():
    agent = FakeAgent({"a": 0.9})
    out = score_chunks("what?", [chunk(1, "a", "s1#0")], agent=agent)
    assert out[0]["laya_p"] == 0.9
    state, questions, max_len = agent.calls[0]
    assert state == "Passage: a"
    assert "what?" in questions["c"]["instructions"]
    assert questions["c"]["type"] == "noul"
    assert max_len == 1024


def test_filter_ranks_by_probability():
    agent = FakeAgent({"low": 0.1, "high": 0.9, "mid": 0.5})
    chunks = [chunk(1, "low", "s1#0"), chunk(2, "high", "s2#0"), chunk(3, "mid", "s3#0")]
    out = filter_sessions("q", chunks, keep_sessions=2, agent=agent)
    assert [c["id"] for c in out] == [2, 3]


def test_filter_keeps_one_best_chunk_per_session():
    agent = FakeAgent({"weak": 0.2, "strong": 0.8})
    chunks = [chunk(1, "weak", "s1#0"), chunk(2, "strong", "s1#1"), chunk(3, "weak", "s2#0")]
    out = filter_sessions("q", chunks, keep_sessions=5, agent=agent)
    sessions = [c["locator"].split("#")[0] for c in out]
    assert len(sessions) == len(set(sessions)) == 2
    assert out[0]["id"] == 2


def test_filter_empty_input_does_not_load_model():
    assert filter_sessions("q", []) == []


def test_filter_without_laya_raises_clear_error(monkeypatch):
    import kodand.rerank as r

    monkeypatch.setattr(r, "_load", lambda path: (_ for _ in ()).throw(RuntimeError("laya is not installed")))
    with pytest.raises(RuntimeError, match="laya"):
        filter_sessions("q", [chunk(1, "a", "s1#0")])


class BatchAgent(FakeAgent):
    def __init__(self, table):
        super().__init__(table)
        self.batches = []

    def predict_batch(self, states, questions, batch_size=None, max_len=1024):
        self.batches.append((list(states), batch_size))
        return [{"answers": {"c": {"noul": self.table.get(s.removeprefix("Passage: "), 0.0)}}}
                for s in states]


def test_batching_preserves_order():
    agent = BatchAgent({"a": 0.1, "b": 0.9, "c": 0.5})
    chunks = [chunk(1, "a", "s1#0"), chunk(2, "b", "s2#0"), chunk(3, "c", "s3#0")]
    out = score_chunks("q", chunks, agent=agent)
    assert [c["laya_p"] for c in out] == [0.1, 0.9, 0.5]

def test_session_timestamp_prefers_content_dates_over_created_at():
    from kodand.rerank import session_timestamp
    group = [{"content": "[q1-session-2 10:20 am on 20 May, 2023] user: hello",
              "created_at": 100},   # import stamp, later than the real date
             {"content": "[q1-session-2 3:25 am on 30 May, 2023] user: run update",
              "created_at": 100}]
    ts = session_timestamp(group)
    from datetime import datetime
    assert abs(ts - datetime(2023, 5, 30, 3, 25).timestamp()) < 60  # noqa: DTZ001


def test_session_timestamp_falls_back_to_created_at():
    from kodand.rerank import session_timestamp
    group = [{"content": "no date inside", "created_at": 1234.0}]
    assert session_timestamp(group) == 1234.0


def test_recency_band_breaks_ties_only():
    agent = _FakeAgent({"late": 0.50, "early": 0.50, "mid": 0.40})
    chunks = [
        {"id": 1, "content": "early [old event on 1 May, 2023]", "locator": "s_old#0", "created_at": 1},
        {"id": 2, "content": "late [newer event on 9 May, 2023]", "locator": "s_new#0", "created_at": 2},
        {"id": 3, "content": "mid [mid event on 5 May, 2023]", "locator": "s_mid#0", "created_at": 3},
    ]
    out = rank_sessions("q?", chunks, keep_chunks=10, recency_band=0.10,
                        session_budget=3, recency=True, agent=agent)
    ids = [c["id"] for c in out]
    # s_old and s_new tie at 0.50 -> newer session first; s_mid trails at 0.40
    assert ids[:2] == [2, 1], ids


def test_recency_offset_does_not_reorder_clear_winners():
    agent = _FakeAgent({"weak": 0.10, "strong": 0.90})
    chunks = [
        {"id": 1, "content": "strong [fresh on 9 May, 2023]", "locator": "s1#0", "created_at": 2},
        {"id": 2, "content": "weak [stale on 1 May, 2023]", "locator": "s2#0", "created_at": 9},
    ]
    out = rank_sessions("q?", chunks, keep_chunks=10, recency_band=0.10,
                        session_budget=2, recency=True, agent=agent)
    assert [c["id"] for c in out][:1] == [1]  # 0.90 >> 0.10: relevance dominates


class _FakeAgent:
    def __init__(self, table):
        self.table = table

    def predict(self, state, questions, max_len=1024):
        text = state.removeprefix("Passage: ")
        best = max((v for k, v in self.table.items() if k in text), default=0.0)
        return {"answers": {"c": {"noul": best}}}

    def predict_batch(self, states, questions, batch_size=None, max_len=1024):
        return [self.predict(s, questions, max_len) for s in states]
