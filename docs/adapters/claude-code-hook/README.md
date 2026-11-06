# Claude Code adapter (hooks + MCP)

Three-piece install, zero plugin plumbing:

1. **MCP server** for Claude Code's native MCP layer (already shipped in kodand):
   ```sh
   claude mcp add kodand -- kodand mcp --repo ~/.kodand/sessions
   ```
   Gives Claude `kodand_remember`, `kodand_recall`, etc. as MCP tools.

2. **Session-start hook** writes the laya briefing (optional). `hooks.json` shape:
   ```json
   { "hooks": { "SessionStart": [
     { "matcher": "startup",
       "hooks": [ { "type": "command",
                    "command": "bash ~/.agents/hooks/kodand-brief.sh \"$CLAUDE_PROJECT_DIR\"" } ] } ] } }
   ```

3. **`kodand-brief.sh`** (in this folder): queries `~/.kodand/<project>/` with a hook script
   (KODAND_PROJECT env-safe), prints at most ~10 lines. Respects `KODAND_BASELINE=1`.

## Which pieces to install

| goal | install |
|---|---|
| Hear/see memory only | piece 1 |
| Recall + rerank before a task starts | pieces 1 + 2 |
| Full local pipeline (laya + daemon warm) | `kodand recalld &`, `laya-serve &`, then pieces as above |
