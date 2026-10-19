"""bench/repeat/score.py — repetition-rate report from results.jsonl."""
import json
import sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else "results.jsonl"
by_arm = defaultdict(lambda: {"n": 0, "rep": 0, "skipped": 0})
with open(path) as f:
    for line in f:
        r = json.loads(line)
        a = by_arm[r["arm"]]
        if r.get("skipped"):
            a["skipped"] += 1
            continue
        a["n"] += 1
        a["rep"] += 1 if r.get("repeated") else 0
print("arm, n, repeated, repetition_rate, skipped")
for arm, s in sorted(by_arm.items()):
    rate = s["rep"] / s["n"] if s["n"] else float("nan")
    print(f"{arm}, {s['n']}, {s['rep']}, {rate:.3f}, {s['skipped']}")
print("\nRule: publish this table with failures; pre-register margin = 15pp")
print("kodand-enforce vs best advisory arm before claiming a win.")
