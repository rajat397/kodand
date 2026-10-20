"""bench/repeat/score.py — repetition-rate report from results jsonl."""
import json
import sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else "results.jsonl"
by_arm = defaultdict(lambda: {"n": 0, "rep": 0, "skipped": 0, "done": 0,
                              "rep_c": 0, "n_c": 0})
with open(path) as f:
    for line in f:
        r = json.loads(line)
        a = by_arm[r["arm"]]
        if r.get("skipped"):
            a["skipped"] += 1
            continue
        a["n"] += 1
        a["rep"] += 1 if r.get("repeated") else 0
        if not r.get("abstained", False):
            a["n_c"] += 1
            a["rep_c"] += 1 if r.get("repeated") else 0
        if r.get("completed"):
            a["done"] += 1
print("arm, n, rep, rate | completed-only | completed, skipped")
for arm, s in sorted(by_arm.items()):
    rate = s["rep"] / s["n"] if s["n"] else float("nan")
    rate_c = s["rep_c"] / s["n_c"] if s["n_c"] else float("nan")
    print(f"{arm}, n={s['n']} rep={s['rep']} rate={rate:.3f} "
          f"| completed-only: n={s['n_c']} rate={rate_c:.3f} "
          f"| completed={s['done']} skipped={s['skipped']}")
print("\nRule: publish this table with failures; pre-register margin = 15pp")
print("kodand-enforce vs best advisory arm before claiming a win.")
print("Abstained (agent wrote nothing) rows count as HELD in the primary")
print("rate and are broken out via the completed-only column.")
