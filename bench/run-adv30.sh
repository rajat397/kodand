#!/bin/bash
# Rapid 5-min loop on adversarial 30 — same model, same harness, offline retrieval
# Usage: ./bench/run-adv30.sh [runId]  (default adv30-$(date +%s))
set -e
RUNID=${1:-adv30-$(date +%s)}
IDS_FILE="/home/rajat/kodand/bench/adversarial-30.json"
echo "Adversarial 30: $RUNID — $(jq -r '.adversarial30 | length' $IDS_FILE) questions"
export NVIDIA_API_KEY="$(python3 -c "import json; print(json.load(open('/home/rajat/.local/share/opencode/auth.json'))['nvidia']['key'])")"
export KODAND_BIN="/home/rajat/.local/bin/kodand"
# No Google free-tier — use Nemotron Lightning (fast, quota-free, offline retrieval is the test)
cd /home/rajat/memorybench
exec bun run src/index.ts run -p kodand -b longmemeval -j nvidia/nemotron-3.5-lightning-30b-a3b -m nvidia/nemotron-3.5-lightning-30b-a3b -r "$RUNID" --question-ids "$IDS_FILE"
# Holdout (never tune on it): jq -r '.holdout30 | join(",")' bench/adversarial-30.json
