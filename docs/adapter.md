# Integrating kodand into any coding agent

kodand stays a small, boring local service. All agents get the same two primitives:

| primitive | command | contract |
|---|---|---|
| **capture** (write) | `kodand remember / capture-tick / mcp` | writes session chunks + HCIL summaries into a repo-scoped sqlite |
| **recall** (read) | `kodand recall --repo <repo> --query <q> --json [--laya-filter]` | returns an ordered array of chunks (optional laya session-rerank); explainable via `laya_p` / `session_p` fields |

Two integration shapes exist — pick by what your harness supports:

- **Daemon shape** (recommended for interactive agents): once per boot run `kodand recalld`
  (TCP :8766) and, for the rerank, `kodand rerank-serve` (TCP :8765). Recall calls cost
  ~0.3–0.5 s; the laya scoring server costs ~30 s once for the model load, then ~10–15 s per
  query amortizable across turns. Systemd user units for both are in
  `docs/adapters/systemd-units/`.
- **One-shot shape** (zero-config, slower): call the CLI directly per query. Each spawn pays
  ~16 s of Python startup — acceptable for hooks that run rarely, not for hot recall paths.

Environment contract (both shapes):

```
KODAND_LAYA_URL=127.0.0.1:8765      # optional; enables laya session-rerank
KODAND_RECALL_URL=127.0.0.1:8766    # optional; zero-spawn recall
KODAND_BASELINE=1                   # kill switch: bypasses laya entirely, serves FTS-only
KODAND_LAYA_MODEL=/path/to/laya     # checkpoint dir (default ~/laya/multilingual)
```

Adapters in this folder are reference implementations (~50–60 lines each); copy, adapt,
and remove everything you don't use:

- [`opencode-plugin/`](opencode-plugin/) — opencode plugin: ingest + recall via daemons
- [`claude-code-hook/`](claude-code-hook/) — Claude Code hook + MCP trio
- [`raw-pipe/`](raw-pipe/) — no harness at all: plain shell for anything that can exec

Every adapter respects `KODAND_BASELINE=1` and never writes live memory into the kodand
repo itself (your data lives in your process' `-repo` dir).
