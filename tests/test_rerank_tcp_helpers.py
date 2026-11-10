import threading

import pytest

from kodand.rerank import build_tcp_server, filter_via_socket


class _Fake:
    """Stand-in agent so no model loads in tests."""

    def __init__(self, table):
        self.table = table

    def predict(self, state, questions, max_len=1024):
        text = state.removeprefix("Passage: ")
        # Session text joins chunk texts; a real model reacts to any of them.
        best = max((v for k, v in self.table.items() if k in text), default=0.0)
        return {"answers": {"c": {"noul": best}}}


def test_tcp_roundtrip_with_fake_agent():
    chunks = [{"id": 1, "content": "pref", "locator": "s1#0", "scope": "repo"},
              {"id": 2, "content": "off", "locator": "s2#0", "scope": "repo"}]

    server = build_tcp_server("127.0.0.1", 0, agent=_Fake({"pref": 0.9, "off": 0.0}))
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        # chunk mode (explicit) keeps the legacy contract
        out = filter_via_socket(
            "What theme?", chunks, url=f"127.0.0.1:{port}", keep_sessions=2, mode="chunks"
        )
        assert [c["id"] for c in out] == [1, 2]
        assert out[0]["laya_p"] == 0.9

        # session mode (default): rank sessions, return ALL their chunks,
        # capped by the chunk budget.
        multi = [{"id": 1, "content": "a", "locator": "s1#0"}, {"id": 2, "content": "b", "locator": "s1#1"},
                 {"id": 3, "content": "c", "locator": "s2#0"}]
        fake = _Fake({"a": 0.2, "b": 0.8, "c": 0.5})
        server2 = build_tcp_server("127.0.0.1", 0, agent=fake)
        port2 = server2.server_address[1]
        t2 = threading.Thread(target=server2.serve_forever, daemon=True)
        t2.start()
        try:
            out2 = filter_via_socket("q?", multi, url=f"127.0.0.1:{port2}", keep_chunks=10)
            # session s1 scored on its best chunk (0.8) ranks above s2 (0.5);
            # both s1 chunks travel together (input/BM25 order) before s2's.
            assert [c["id"] for c in out2] == [1, 2, 3]
            assert out2[0]["session_p"] == 0.8
        finally:
            server2.shutdown()
            server2.server_close()
            t2.join(timeout=5)
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=5)


def test_socket_without_server_raises_hint():
    with pytest.raises(RuntimeError, match="rerank-serve"):
        filter_via_socket("q", [{"id": 1, "content": "a", "locator": "s1#0"}],
                          url="127.0.0.1:1", timeout=2.0)
