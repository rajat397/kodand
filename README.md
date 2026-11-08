# kodand

kodand = persistent, explainable memory plane for coding agents — SQLite-local storage, session-aware CPU decision-model rerank, safety gates in the box, an adapter for any harness that can shell out.

## Quickstart (pip, 60 seconds)

```sh
pip install kodand                    # zero-dep core: FTS recall
pip install "kodand[laya]"            # CPU decision-model rerank tier
kodand fetch-model                    # ~644 MB checkpoint, sha-verified -> ~/.kodand/
kodand rerank-serve &                 # scoring daemon, ~830 MB, once per boot
KODAND_LAYA_URL=127.0.0.1:8765 kodand recall --repo . --query "..." --laya-filter --json
```

Kill switch: `KODAND_BASELINE=1` reverts retrieval to plain FTS for every consumer in one env var.
Adapter examples (opencode plugin ~60 lines, Claude Code hooks, raw pipe, systemd units) live in
`docs/adapter.md` + `docs/adapters/`.

## Install

```bash
pip install kodand
kodand init
kodand install opencode   # or claude-code, cursor, windsurf, qoder, vscode, all
```

## Commands

- `kodand init` - Initialize kodand for a repo
- `kodand install <harness>` - Install for a harness
- `kodand remember` - Store a memory entry
- `kodand recall` - Search and recall memories
- `kodand rerank` - One-shot filter of recall results with the Laya decision model
- `kodand rerank-serve` - TCP rerank server for `recall --laya-filter`
- `kodand trust-list` - List trust surface entries
- `kodand capture-tick` - Run capture tick
- `kodand mcp` - Start MCP server
- `kodand dashboard` - Start local dashboard
- `kodand doctor` - Check installation

## Laya retrieval filter

Score candidate chunks with a small decision model (Laya, CPU-only) and keep
the best chunk of the top-k sessions by P(help answers the question); relative
ranking, never an absolute threshold. Session evidence recall@10 on a
20-question LongMemEval split: 0.520 -> 0.718 with `--keep 8`
(see `bench/reports/laya-gate1.md`).

```sh
kodand rerank-serve &                       # once; single model load, ~30s
KODAND_LAYA_URL=127.0.0.1:8765 kodand recall --repo . --query "..." --laya-filter
```

Optional env: `KODAND_LAYA_URL` (default `127.0.0.1:8765`), `KODAND_LAYA_MODEL`
(checkpoint dir). Tradeoff: ~11s extra CPU scoring at the default `limit=10`
on 2 cores; scales with limit.

## Plug into your coding agent

Three reference adapters, one contract (stdout = JSON chunk array, best-first, `KODAND_BASELINE=1` kill switch honoured):

```sh
# plugin for opencode, hooks for Claude Code, or any shell:
pip install kodand
# write + recall with session-rerank, whole flow:
KODAND_LAYA_URL=127.0.0.1:8765 kodand recall --repo . --query "..." --laya-filter --json
```

See [docs/adapter.md](docs/adapter.md) and [docs/adapters/](docs/adapters/) for the
opencode plugin (~60 lines), Claude Code hook, raw-pipe and optional systemd units.

## Layout metric honesty + measured results

All claims cite committed run reports under `bench/reports/`.

LongMemEval-500, identical judge/answering (nvidia/nemotron-3.5-lightning-30b-a3b):
- plain FTS baseline: accuracy 270/500 (0.540), evidence recall@10 **0.862**
- shipped hybrid (BM25 seeds + laya session fills, budget 10): accuracy **284/500 (0.568)**
  (McNemar 43/57 discordant, p=0.19 — directional, not proven), evidence recall 0.825
- honest tradeoff: the rerank wins hard on adversarial splits and gives up a recorded
  ~3.7pp evidence coverage on standard text; not hidden anywhere.

## Safety in the box

- secrets blocked on every write path (detector list in `kodand/scope.py`)
- 32-prompt x 4-category prompt-injection corpus + zero-hit scanner (`bench/safety/`)
- per-chunk provenance: `session_p` (relevance) always inspectable in stdout JSON
- kill switch honored by CLI and daemons (tested; p95=113ms fallback)

## What kodand does NOT do

- never sends data anywhere (stores and reads everything locally)
- never executes recalled content as instructions; it returns text, nothing more

## License

Apache-2.0
