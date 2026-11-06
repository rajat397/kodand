#!/usr/bin/env bash
# kodand brief hook for Claude Code / any hook-capable harness (KODAND_PROJECT_DIR-aware).
# Prints at most 8 remembered lines matching the project path; silent when nothing exists.
set -u
dir="${KODAND_PROJECT_DIR:-$1}"
[ -n "$dir" ] || exit 0
repo="$HOME/.kodand/$(echo "$dir" | tr '/.' '__')"
[ -d "$repo" ] || exit 0                        # nothing remembered yet -> silent
q=$(basename "$dir")
if [ -n "${KODAND_RECALL_URL:-}" ] && ! [ "${KODAND_BASELINE:-}" = "1" ]; then
  python3 - "$KODAND_RECALL_URL" "$repo" "$q" <<'PY'
import json,socket,sys
host,_,port=sys.argv[1].replace("//","").partition(":")
s=socket.create_connection((host or "127.0.0.1",int(port or 8766)),timeout=8); s.settimeout(30)
s.sendall(json.dumps({"repo":sys.argv[2],"query":sys.argv[3],"k":8}).encode()+b"\n")
buf=b""
while b"\n" not in buf: buf+=s.recv(65536)
for r in json.loads(buf).get("rows",[]): print("-", r.get("content","")[:200])
PY
else
  kodand recall --repo "$repo" --query "$q" --limit 8 --json 2>/dev/null \
    | python3 -c 'import json,sys
for r in json.load(sys.stdin)[:8]: print("-", r.get("content","")[:200])'
fi
