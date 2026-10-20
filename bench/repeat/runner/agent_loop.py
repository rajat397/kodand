"""
bench/repeat/runner/agent_loop.py — fresh-session agent-loop benchmark (stdlib only).

Each (arm, task, run): fresh temp repo with a scaffold (no mistake), arm context
applied, then a tool-calling agent (local Ollama, pinned snapshot) performs the
retest task. Grader decides: mistake pattern present => repeated.

Records-first: every row appended to results JSONL immediately, with a transcript
file per row. Resumable via --resume (skips completed keys). Model arms needing
external APIs are NOT faked.

Usage:
  python3 runner/agent_loop.py --verify5 [--tag v4] [--model qwen2.5:1.5b]
  python3 runner/agent_loop.py --tasks 32 --runs 3 --resume
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PATH = os.path.join(HERE, "..", "tasks", "tasks32.json")
RESULTS_PATH = os.path.join(HERE, "..", "results_agent.jsonl")
TRANSCRIPTS_DIR = os.path.join(HERE, "..", "transcripts")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
MODEL_SNAPSHOT = os.environ.get("MODEL_SNAPSHOT", "qwen2.5:1.5b")
MAX_STEPS = 8

ARMS = ["no-memory", "agents-md", "kodand-inject", "kodand-enforce"]

TOOLS = [
    {"type": "function", "function": {
        "name": "list_files",
        "description": "List files in the repo.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a file's content. path must be a FILE like 'svc.py', never a directory or empty.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write (create or overwrite) a FILE. path must be a file like 'svc.py' with full new content, never a directory or empty.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "run_grader",
        "description": "Run the repo's task grader; returns PASS or FAIL.",
        "parameters": {"type": "object", "properties": {}}}},
]


def ollama_chat(model, messages, tools=None):
    body = {"model": model, "messages": messages, "stream": False,
            "options": {"temperature": 0}}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        OLLAMA_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode())


def run_grader(repo, task):
    try:
        r = subprocess.run(task["grader"], shell=True, cwd=repo,
                           capture_output=True, timeout=30)
        passed = (r.returncode == task["grade_pass_exit"])
        return "PASS" if passed else "FAIL", passed
    except Exception as e:
        return f"ERROR: {e}", False


def apply_arm(repo, arm, task):
    """Apply arm context. Returns (context_text, note). Uses real kodand for kodand arms."""
    sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))
    if arm == "no-memory":
        return "", ""
    if arm == "agents-md":
        with open(os.path.join(repo, "AGENTS.md"), "w") as f:
            f.write(f"# Agent guidance (repo policy)\n\n{task['correction']}\n")
        return "Follow AGENTS.md in the repo.", ""
    if arm in ("kodand-inject", "kodand-enforce"):
        from kodand.store import get_store
        s = get_store(repo)
        e = s.remember(content=task["correction"], surface="text",
                       locator=task["locator"], scope="repo")
        extra = ""
        if arm == "kodand-enforce":
            from kodand.enforcement import create_enforcement_ladder
            lad = create_enforcement_ladder(repo)
            ok = lad.promote(e["key"], "test")
            extra = (" The repo has kodand enforcement tests (tests/test_kodand_*.py)"
                     " encoding past corrections. Use run_grader before finishing"
                     " and fix any failure.")
            return (f"Relevant memories from past sessions:\n- {task['correction']}" + extra,
                    f"enforce artifact written={ok}")
        return f"Relevant memories from past sessions:\n- {task['correction']}", ""
    raise AssertionError(arm)


def do_tool(repo, task, name, args):
    if name == "list_files":
        out = []
        for root, dirs, files in os.walk(repo):
            dirs[:] = [d for d in dirs if d not in (".git", ".kodand", "__pycache__")]
            for fn in files:
                out.append(os.path.relpath(os.path.join(root, fn), repo))
        return "files:\n" + "\n".join(sorted(out)[:50])
    if name == "read_file":
        p = os.path.normpath(os.path.join(repo, args.get("path", "")))
        if not p.startswith(os.path.abspath(repo)):
            return "ERROR: path escapes repo"
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                return f.read()[:4000]
        except Exception as e:
            return f"ERROR: {e}"
    if name == "write_file":
        p = os.path.normpath(os.path.join(repo, args.get("path", "")))
        if not p.startswith(os.path.abspath(repo)):
            return "ERROR: path escapes repo"
        try:
            os.makedirs(os.path.dirname(p) or repo, exist_ok=True)
            with open(p, "w") as f:
                f.write(args.get("content", ""))
            return "WROTE " + args.get("path", "")
        except Exception as e:
            return f"ERROR: {e}"
    if name == "run_grader":
        verdict, _ = run_grader(repo, task)
        return f"grader: {verdict}"
    return f"ERROR: unknown tool {name}"


def agent_run(repo, task, arm_ctx, model):
    """Tool loop. Returns (transcript, steps, duration_s)."""
    transcript = []
    system = ("You are a coding agent working in a small repo. Complete the user's "
              "task with minimal changes using the provided tools. "
              "Workflow: 1) list_files 2) read_file on the task file "
              "3) write_file to the SAME file path with the full new content "
              "4) run_grader to check 5) reply with exactly: DONE. "
              "Always pass a file path like 'svc.py', never a directory or empty path.")
    if arm_ctx:
        system += "\n\n" + arm_ctx
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": task["retest"]}]
    t0 = time.time()
    steps = 0
    try:
        for _ in range(MAX_STEPS):
            resp = ollama_chat(model, messages, TOOLS)
            msg = resp.get("message", {})
            if msg.get("tool_calls"):
                messages.append({"role": "assistant", "content": msg.get("content", ""),
                                 "tool_calls": msg.get("tool_calls")})
            else:
                messages.append({"role": "assistant", "content": msg.get("content", "")})
            calls = msg.get("tool_calls") or []
            tools_used = any(x.get("turn", "").startswith("tool:") for x in transcript)
            if not calls:
                transcript.append({"turn": "final", "text": (msg.get("content") or "")[:500]})
                if "DONE" in (msg.get("content") or "") and tools_used:
                    break
                nudges = sum(1 for x in transcript if x.get("turn") == "nudge")
                if nudges < 2:
                    transcript.append({"turn": "nudge", "text": "do-the-task"})
                    messages.append({"role": "user",
                                     "content": "You have not changed any file yet. Use list_files, "
                                     "read_file, write_file to do the task, optionally run_grader, "
                                     "then reply DONE."})
                    continue
                break
            for call in calls:
                steps += 1
                fn = call.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments", {})
                try:
                    args = (raw_args if isinstance(raw_args, dict)
                            else json.loads(raw_args or "{}"))
                except Exception:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                out = do_tool(repo, task, name, args)
                transcript.append({"turn": f"tool:{name}", "args": str(args)[:200],
                                   "out": out[:300]})
                messages.append({"role": "tool", "content": out})
                if steps >= MAX_STEPS:
                    break
    except Exception as e:
        transcript.append({"turn": "error", "text": str(e)[:300]})
    return transcript, steps, round(time.time() - t0, 1)


def run_once(arm, task, run_idx, model, results_path, transcripts_dir):
    key = f"{arm}/{task['id']}/r{run_idx}"
    with tempfile.TemporaryDirectory() as repo:
        subprocess.run(["git", "init", "-q"], cwd=repo, capture_output=True)
        with open(os.path.join(repo, task["target_file"]), "w") as f:
            f.write(task["scaffold"])
        arm_ctx, note = apply_arm(repo, arm, task)
        transcript, steps, dur = agent_run(repo, task, arm_ctx, model)
        _, absent = run_grader(repo, task)
        with open(os.path.join(repo, task["target_file"])) as f:
            final = f.read()
        completed = final != task["scaffold"]
        row = {
            "arm": arm, "task": task["id"], "run": run_idx, "model": model,
            "mistake_absent": absent, "repeated": not absent,
            "completed": completed, "abstained": not completed,
            "steps": steps, "duration_s": dur, "note": note,
        }
    os.makedirs(transcripts_dir, exist_ok=True)
    tpath = os.path.join(transcripts_dir, key.replace("/", "_") + ".json")
    with open(tpath, "w") as f:
        json.dump(transcript, f)
    row["transcript"] = os.path.relpath(tpath, os.path.join(HERE, ".."))
    with open(results_path, "a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def load_done(results_path):
    done = set()
    if os.path.exists(results_path):
        with open(results_path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done.add((r["arm"], r["task"], r["run"]))
                except Exception:
                    continue
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=32)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--arms", nargs="*", default=ARMS)
    ap.add_argument("--model", default=MODEL_SNAPSHOT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--verify5", action="store_true")
    ap.add_argument("--tag", default="",
                    help="suffix for results/transcript files, e.g. --tag v4")
    args = ap.parse_args()

    results_path = (RESULTS_PATH if not args.tag
                    else RESULTS_PATH.replace(".jsonl", f"_{args.tag}.jsonl"))
    transcripts_dir = (TRANSCRIPTS_DIR if not args.tag
                       else f"{TRANSCRIPTS_DIR}_{args.tag}")

    with open(TASKS_PATH) as f:
        spec = json.load(f)
    tasks = spec["tasks"][:args.tasks]
    done = load_done(results_path) if args.resume else set()

    combos = []
    if args.verify5:
        combos = [("no-memory", tasks[0], 0), ("agents-md", tasks[0], 0),
                  ("kodand-inject", tasks[4], 0), ("kodand-enforce", tasks[4], 0),
                  ("kodand-enforce", tasks[12], 0)]
    else:
        for t in tasks:
            for arm in args.arms:
                for r in range(args.runs):
                    combos.append((arm, t, r))
    if args.limit:
        combos = combos[:args.limit]
    combos = [c for c in combos if (c[0], c[1]["id"], c[2]) not in done]

    print(f"model={args.model} combos={len(combos)} results={results_path}", flush=True)
    for i, (arm, task, r) in enumerate(combos):
        row = run_once(arm, task, r, args.model, results_path, transcripts_dir)
        print(f"[{i+1}/{len(combos)}] {arm:15} {task['id']:20} "
              f"{'REPEATED' if row['repeated'] else 'HELD'} "
              f"completed={row['completed']} steps={row['steps']} {row['duration_s']}s",
              flush=True)


if __name__ == "__main__":
    main()
