"""
kodand.hooks - Prospective recall hook (Iter 7, C3)
Reuses C7 before-tool plumbing: inject matching entries when file touched / command run / dep added.
"""
import time
import json
from kodand.recall import create_recall_engine
from kodand.measure import log_event

# Tools that trigger prospective recall
FILE_TOOLS = {"read", "write", "edit", "apply_patch", "view"}
CMD_TOOLS = {"bash", "run_command", "exec"}
DEP_TOOLS = {"add_dependency", "install", "npm_install", "pip_install"}

def before_tool(tool: str, args: dict, repo_path=None):
    """Hook entry — call before tool execution. Returns list of entries to inject or [].
    Never raises, never blocks — amplify, never restrict.
    """
    start = time.time()
    try:
        engine = create_recall_engine(repo_path)
        ctx = {}
        tool_l = (tool or "").lower()
        # file touched
        if tool_l in FILE_TOOLS or "file" in str(args).lower():
            for k in ("file", "file_path", "path", "filepath"):
                if k in args and args[k]:
                    ctx["file_path"] = args[k]
                    break
        # command run
        if tool_l in CMD_TOOLS or "command" in args or "cmd" in args:
            ctx["command"] = args.get("command") or args.get("cmd") or args.get("input") or ""
        # dependency added
        if tool_l in DEP_TOOLS or "dependency" in args or "package" in args:
            ctx["command"] = args.get("package") or args.get("dependency") or ctx.get("command","")
        if not ctx:
            return []
        hits = engine.prospective_recall(ctx)
        # precision tracking: log injected
        for h in hits[:3]:  # cap injected to 3 to keep latency/budget
            log_event(repo_path, "injected", h["id"], f"prospective:{tool}", json.dumps({"tool": tool, "match": h.get("locator","")}))
        # cost log
        latency = int((time.time()-start)*1000)
        log_event(repo_path, "cost", None, "prospective", json.dumps({"latency_ms": latency, "hits": len(hits)}))
        return hits[:3]
    except Exception as e:
        # fail-open
        try:
            log_event(repo_path, "held", None, "prospective:hook-error", str(e)[:200])
        except Exception:
            pass
        return []
