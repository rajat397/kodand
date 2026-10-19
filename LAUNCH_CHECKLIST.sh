#!/bin/bash
set -e
echo "=== LAUNCH CHECKLIST ==="
kodand --help | head -1
echo "--- 2 Init ---"
rm -rf /tmp/chk && mkdir -p /tmp/chk && cd /tmp/chk && git init -q && git config user.email "t@t" && git config user.name "t" && echo "x" > a.txt && git add . && git commit -qm "init"
kodand init . --min-commits 0 2>&1 | head -1
echo "--- 3 Remember ---"
kodand remember --repo . --title "T" --content "Use DI" --file "di.py" 2>&1 | head -1
echo "--- 4 Recall ---"
kodand recall --repo . --query "Use" 2>&1 | head -2
echo "--- 5 Prospective ---"
kodand hook --repo . --tool write --args-json '{"file_path":"di.py"}' 2>&1 | head -2
echo "--- 6 Warm-start ---"
kodand warm-start --repo . 2>&1 | head -3
echo "--- 7 Trust ---"
kodand trust-list --repo . 2>&1 | head -2
echo "--- 10 Capture ---"
kodand capture-tick --repo . 2>&1
echo "--- 11 Anchor ---"
kodand anchor --repo . --file "di.py" 2>&1 | head -2
echo "--- 12 Manifest ---"
echo '{"dependencies":{"express":"4.0.0"}}' > package.json; kodand manifest-watch --repo . 2>&1 | head -1
echo '{"dependencies":{"express":"5.0.0"}}' > package.json; kodand manifest-watch --repo . 2>&1 | head -1
echo "--- 13 Team drill ---"
kodand team-promote --repo . --drill 2>&1
echo "--- 14 Swarm ---"
kodand swarm-claim --repo . --resource "a.txt" --session s1 2>&1
kodand swarm-claim --repo . --resource "a.txt" --session s2 2>&1
echo "--- 17 Week ---"
kodand week --repo . 2>&1 | head -3
echo "--- 19 Doctor ---"
kodand doctor --repo . 2>&1 | tail -2
echo "=== ALL CHECKS PASSED ==="
