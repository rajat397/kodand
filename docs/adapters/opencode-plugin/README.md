# OpenCode plugin adapter (~60 lines)

Drop-in plugin: write session text, recall enriched context for the next turn. Zero
daemon dependency (falls back to CLI if the TCP ports are closed).

## Install

```sh
mkdir -p ~/.config/opencode/plugins
cp kodand-adapter.ts ~/.config/opencode/plugins/kodand.ts
```

## Emitting memory (optional)

The plugin recalls when an env var is set; call `recall("query")` from any prompt.
`~/.kodand/repo-$(pwd-hash)/` is your work-repo memory store (nothing touches kodand's repo).
Deliberately NOT auto-ingesting sessions — that's a separate hook habit so trust/gameable
memory starts opt-in.
