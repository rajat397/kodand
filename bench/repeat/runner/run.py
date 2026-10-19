"""
bench/repeat/runner/run.py — repeated-mistake benchmark runner (skeleton, honest).

Arms (7 registered; model-backed arms SKIP with an explicit note when their
requirements are absent — never faked):
  no-memory | agents-md | kodand-inject | kodand-enforce   -> run locally now
  native-auto | mem0 | claude-mem                         -> require harness/API, skipped openly

Protocol per (arm, task): fresh temp repo, plant mistake, apply arm, run grader.
Grader exit == grade_pass_exit means the mistake is ABSENT (arm held).
Anything else counts as a repetition. Results -> results.jsonl, one row per run.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PATH = os.path.join(HERE, "..", "tasks", "tasks.json")
RESULTS_PATH = os.path.join(HERE, "..", "results.jsonl")

MODEL_SNAPSHOT = os.environ.get("MODEL_SNAPSHOT", "opencode-go/muse-spark-1.3-contributor")

LOCAL_ARMS = ["no-memory", "agents-md", "kodand-inject", "kodand-enforce"]
SKIPPED_ARMS = {
    "native-auto": "requires harness auto-memory session (not wired in skeleton)",
    "mem0": "requires MEM0_API_KEY + mem0 MCP (absent)",
    "claude-mem": "requires claude-mem harness (absent)",
}


def run_grader(repo: str, task: dict) -> bool:
    """True when the mistake is ABSENT (grader exit == grade_pass_exit)."""
    try:
        r = subprocess.run(task["grader"], shell=True, cwd=repo,
                           capture_output=True, timeout=30)
        return r.returncode == task["grade_pass_exit"]
    except Exception:
        return False


def apply_arm(repo: str, arm: str, task: dict) -> dict:
    """Apply the arm's memory mechanism. Returns {held: bool|None, note}."""
    sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))
    if arm == "no-memory":
        return {"held": None, "note": "no memory: mistake stays planted"}
    if arm == "agents-md":
        with open(os.path.join(repo, "AGENTS.md"), "w") as f:
            f.write(f"# Agent guidance\n\n{task['correction']}\n")
        return {"held": None, "note": "advisory context only; grader decides"}
    if arm in ("kodand-inject", "kodand-enforce"):
        from kodand.store import get_store
        from kodand.enforcement import create_enforcement_ladder
        s = get_store(repo)
        e = s.remember(content=task["correction"], surface="text",
                       locator=task["locator"], scope="repo")
        if arm == "kodand-enforce":
            lad = create_enforcement_ladder(repo)
            ok = lad.promote(e["key"], "test")
            return {"held": None, "note": f"enforce artifact written={ok}"}
        return {"held": None, "note": "injected to store; no blocking artifact"}
    raise AssertionError(f"unknown local arm {arm}")


def run_once(arm: str, task: dict) -> dict:
    with tempfile.TemporaryDirectory() as repo:
        subprocess.run(["git", "init", "-q"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
        target = os.path.join(repo, task["target_file"])
        with open(target, "w") as f:
            f.write(task["plant"])
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        info = apply_arm(repo, arm, task)
        absent = run_grader(repo, task)
        row = {
            "arm": arm, "task": task["id"], "model": MODEL_SNAPSHOT,
            "mistake_absent": absent, "repeated": not absent,
            "note": info.get("note", ""),
        }
        if arm == "kodand-enforce":
            import glob
            tests = sorted(glob.glob(os.path.join(repo, "tests", "test_kodand_*.py")))
            if tests:
                names = [os.path.relpath(t, repo) for t in tests]
                planted = subprocess.run(
                    ["python3", "-m", "pytest"] + names + ["-q"],
                    cwd=repo, capture_output=True, timeout=60,
                )
                row["block_fires_while_planted"] = planted.returncode != 0
                # Mechanical fix then re-check for false blocks.
                with open(target, "w") as f:
                    f.write("# fixed: correction applied\n")
                fixed = subprocess.run(
                    ["python3", "-m", "pytest"] + names + ["-q"],
                    cwd=repo, capture_output=True, timeout=60,
                )
                row["clean_after_fix"] = fixed.returncode == 0
        return row


def main() -> None:
    with open(TASKS_PATH) as f:
        spec = json.load(f)
    arms = sys.argv[1:] or LOCAL_ARMS
    rows = []
    for arm in arms:
        for task in spec["tasks"]:
            if arm in SKIPPED_ARMS:
                rows.append({"arm": arm, "task": task["id"], "model": MODEL_SNAPSHOT,
                             "skipped": True, "reason": SKIPPED_ARMS[arm]})
                continue
            rows.append(run_once(arm, task))
    with open(RESULTS_PATH, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    # Summary to stdout.
    from collections import defaultdict
    by_arm = defaultdict(lambda: {"n": 0, "rep": 0})
    for r in rows:
        if r.get("skipped"):
            print(f"{r['arm']:15} {r['task']:20} SKIPPED: {r['reason']}")
            continue
        by_arm[r["arm"]]["n"] += 1
        by_arm[r["arm"]]["rep"] += 1 if r["repeated"] else 0
        print(f"{r['arm']:15} {r['task']:20} {'REPEATED' if r['repeated'] else 'HELD'}")
    for arm, s in by_arm.items():
        print(f"{arm}: repetition_rate={s['rep']}/{s['n']}={s['rep']/s['n']:.2f}")
    print(f"model_snapshot={MODEL_SNAPSHOT}")
    print(f"results -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
