# Raw pipe adapter (no harness required anything)

Any harness that can run a shell can use kodand. No daemons, no plugin format.

```sh
# one-time: remember something
kodand remember --repo ~/.kodand/myproject --content "uses bun, hoisted deps, node 22" 

# recall (plain FTS, ~16 s spawn cost per call)
kodand recall --repo ~/.kodand/myproject --query "which package manager" --limit 8 --json

# recall with laya session-rerank (needs rerank-serve once: `kodand rerank-serve &`)
KODAND_LAYA_URL=127.0.0.1:8765 kodand recall --repo ~/.kodand/myproject \
  --query "which package manager" --laya-filter --json | jq '.[] | {locator, content: .content[0:80], p: .session_p}'
```

## Composability contract

- Stdout is always one JSON array of `{id, content, locator, scope, ...}` chunks,
  ordered best-first when the rerank is on (`session_p` = session relevance).
- Exit codes: 0 on success, 2 on misconfiguration (kill switch honoured, missing query).
- Empty result set = `[]`, never an error — pipe-friendly.

Cron, CI, CI jobs, anything that shells out: this is the whole interface. Start here,
upgrade to [opencode-plugin](../opencode-plugin/) or [claude-code-hook](../claude-code-hook/)
only when you want daemon-warm recall in a hot loop.
