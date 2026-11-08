"""
kodand.cli - Command-line interface for kodand
"""

import argparse
import json
import os
import sys
from pathlib import Path

from kodand.anchor import get_anchored, resolve_anchor
from kodand.capture import CaptureLoop, run_capture_loop, run_capture_tick
from kodand.enforcement import EnforcementLadder
from kodand.handoff import Handoff
from kodand.hooks import before_tool
from kodand.install import init_repo, install_harness, list_harnesses, uninstall_harness
from kodand.manifest import discover_manifests, flag_conventions
from kodand.outcome import create_outcome_labeler
from kodand.recall import create_recall_engine, recall
from kodand.store import get_store
from kodand.swarm import SwarmCoordination
from kodand.team import drill_poison, promote_to_team
from kodand.trust import TrustSurface
from kodand.utility import create_utility_scorer
from kodand.warmstart import create_warm_start, get_warm_context


def main():
    parser = argparse.ArgumentParser(prog="kodand", description="kodand - memory plane for coding agents")
    subparsers = parser.add_subparsers(dest="command")

    # init
    init_p = subparsers.add_parser("init", help="Initialize kodand for a repo")
    init_p.add_argument("path", nargs="?", default=".", help="Repository path")
    init_p.add_argument("--auto-accept", action="store_true", help="Non-interactive mode")
    init_p.add_argument("--min-commits", type=int, default=20, help="Minimum commits required")

    # install
    install_p = subparsers.add_parser("install", help="Install kodand for a harness")
    install_p.add_argument("harness", nargs="?", default="all", help="Harness to install for")
    install_p.add_argument("--check", action="store_true", help="Check installation status")

    # remember
    remember_p = subparsers.add_parser("remember", help="Store a memory entry")
    remember_p.add_argument("--repo", required=True, help="Repository path")
    remember_p.add_argument("--title", required=True, help="Memory title")
    remember_p.add_argument("--content", required=True, help="Memory content")
    remember_p.add_argument("--type", default="reference", help="Memory type")
    remember_p.add_argument("--scope", default="repo", help="Memory scope")
    remember_p.add_argument("--confidence", default="medium", help="Confidence level")
    remember_p.add_argument("--file", help="Anchor to file path")
    remember_p.add_argument("--symbol", help="Anchor to symbol")
    remember_p.add_argument("--tags", help="Comma-separated tags")

    # recall
    recall_p = subparsers.add_parser("recall", help="Search and recall memories")
    recall_p.add_argument("--repo", required=True, help="Repository path")
    recall_p.add_argument("--query", help="Search query")
    recall_p.add_argument("--limit", type=int, default=10, help="Maximum results")
    recall_p.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    recall_p.add_argument("--laya-filter", action="store_true",
                          help="Keep only the best chunk of the top-k sessions judged relevant by the Laya model "
                               "(requires a running `kodand rerank-serve`; override target with KODAND_LAYA_URL)")
    recall_p.add_argument("--keep", type=int, default=8, help="Sessions kept when --laya-filter is on")

    # laya rerank
    rerank_p = subparsers.add_parser("rerank", help="Filter recall results with the Laya decision model")
    rerank_p.add_argument("--repo", help="Repository path (omit to read chunks as JSON on stdin)")
    rerank_p.add_argument("--query", required=True, help="Question used to judge each chunk")
    rerank_p.add_argument("--limit", type=int, default=30, help="Candidates to fetch when --repo is set")
    rerank_p.add_argument("--keep", type=int, default=8, help="Sessions to keep")
    rerank_p.add_argument("--model", help="Laya checkpoint directory")

    # laya rerank server
    rerank_server_p = subparsers.add_parser(
        "rerank-server", help="Long-lived JSONL rerank server (one model load)"
    )
    rerank_server_p.add_argument("--model", help="Laya checkpoint directory")
    rerank_serve_p = subparsers.add_parser(
        "rerank-serve", help="TCP rerank server for `kodand recall --laya-filter`"
    )
    rerank_serve_p.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    rerank_serve_p.add_argument("--port", type=int, default=8765, help="Bind port (default 8765)")
    rerank_serve_p.add_argument("--model", help="Laya checkpoint directory")
    fetch_model_p = subparsers.add_parser(
        "fetch-model", help="Download the laya decision-model checkpoint (verified sha256)"
    )
    fetch_model_p.add_argument("--dest", help="Install dir (default ~/.kodand/models/laya-multilingual)")
    ing_art_p = subparsers.add_parser("ingest-artifact", help="Ingest a file artifact with provenance (K3)")
    ing_art_p.add_argument("--repo", required=True, help="Repository path")
    ing_art_p.add_argument("--path", required=True, help="Artifact file (md/html/code/image/pdf)")
    ing_art_p.add_argument("--caption", default="", help="Free-text caption (required for images)")
    asm_p = subparsers.add_parser("assemble", help="K4 block assembly: stable prefix + append-only memory blocks")
    asm_p.add_argument("--repo", required=True, help="Repository path")
    asm_p.add_argument("--query", required=True, help="The question/prompt for this turn")
    asm_p.add_argument("--prefix-file", required=True, help="Path to the STABLE prefix text (must not change mid-session)")
    asm_p.add_argument("--state-file", required=True, help="Slot table state (freeze block order across turns)")
    asm_p.add_argument("--limit", type=int, default=10, help="Max memory blocks")
    surf_p = subparsers.add_parser("memory-surface", help="K5 visual interactive memory surface (http://127.0.0.1:port)")
    surf_p.add_argument("--repo", required=True, help="Repository path")
    surf_p.add_argument("--port", type=int, default=8881)
    surf_p.add_argument("--host", default="127.0.0.1")
    recalld_p = subparsers.add_parser("recalld", help="TCP recall server (per-repo cache, no spawn per query)")
    recalld_p.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    recalld_p.add_argument("--port", type=int, default=8766, help="Bind port (default 8766)")

    # prospective recall
    prospective_p = subparsers.add_parser("prospective", help="Prospective recall based on context")
    prospective_p.add_argument("--repo", required=True, help="Repository path")
    prospective_p.add_argument("--file", help="File path being touched")
    prospective_p.add_argument("--symbol", help="Symbol being accessed")
    prospective_p.add_argument("--cmd", dest="cmd", help="Command being run")

    # warm-start
    warmstart_p = subparsers.add_parser("warm-start", help="Show warm start context")
    warmstart_p.add_argument("--repo", required=True, help="Repository path")

    # trust-list
    trust_list_p = subparsers.add_parser("trust-list", help="List trust surface entries")
    trust_list_p.add_argument("--repo", required=True, help="Repository path")
    trust_list_p.add_argument("--scope", help="Filter by scope")

    # trust-inspect
    trust_inspect_p = subparsers.add_parser("trust-inspect", help="Inspect a memory entry")
    trust_inspect_p.add_argument("--repo", required=True, help="Repository path")
    trust_inspect_p.add_argument("--id", required=True, type=int, help="Entry ID")

    # trust-correct
    trust_correct_p = subparsers.add_parser("trust-correct", help="Correct a memory entry")
    trust_correct_p.add_argument("--repo", required=True, help="Repository path")
    trust_correct_p.add_argument("--id", required=True, type=int, help="Entry ID")
    trust_correct_p.add_argument("--kind", required=True, help="Correction kind")
    trust_correct_p.add_argument("--note", required=True, help="Correction note")

    # trust-delete
    trust_delete_p = subparsers.add_parser("trust-delete", help="Delete a memory entry")
    trust_delete_p.add_argument("--repo", required=True, help="Repository path")
    trust_delete_p.add_argument("--id", required=True, type=int, help="Entry ID")

    # trust-decay (Iter 8, C5 - retire low-utility)
    trust_decay_p = subparsers.add_parser("trust-decay", help="Retire low-utility entries")
    trust_decay_p.add_argument("--repo", required=True, help="Repository path")
    trust_decay_p.add_argument("--threshold", type=float, default=0.0, help="Utility threshold")
    trust_decay_p.add_argument("--days", type=int, default=7, help="Older than N days")

    # capture-tick
    capture_tick_p = subparsers.add_parser("capture-tick", help="Run capture tick")
    capture_tick_p.add_argument("--repo", required=True, help="Repository path")
    capture_tick_p.add_argument("--ceiling", type=int, default=5, help="Cards per day ceiling")

    # capture-loop
    capture_loop_p = subparsers.add_parser("capture-loop", help="Run capture loop")
    capture_loop_p.add_argument("--repo", required=True, help="Repository path")

    # week
    week_p = subparsers.add_parser("week", help="Weekly value surface")
    week_p.add_argument("--repo", required=True, help="Repository path")
    week_p.add_argument("--week", help="ISO week (YYYY-Www)")

    # doctor
    doctor_p = subparsers.add_parser("doctor", help="Check kodand installation")
    doctor_p.add_argument("--repo", required=True, help="Repository path")

    # outcome-label
    outcome_p = subparsers.add_parser("outcome-label", help="Label an entry with outcome")
    outcome_p.add_argument("--repo", required=True, help="Repository path")
    outcome_p.add_argument("--id", required=True, type=int, help="Entry ID")
    outcome_p.add_argument("--kind", required=True, choices=["avoided_mistake", "caused_mistake", "noise"], help="Outcome kind")
    outcome_p.add_argument("--note", default="", help="Outcome note")
    outcome_p.add_argument("--holdout", action="store_true", help="Mark as holdout for counterfactual")

    # utility
    utility_p = subparsers.add_parser("utility", help="Show utility scores")
    utility_p.add_argument("--repo", required=True, help="Repository path")
    utility_p.add_argument("--limit", type=int, default=10, help="Maximum results")

    # team-promote (Iter 10, C9)
    team_p = subparsers.add_parser("team-promote", help="Promote memory to team scope (quorum + screening)")
    team_p.add_argument("--repo", required=True, help="Repository path")
    team_p.add_argument("--id", required=False, type=int, help="Entry ID")
    team_p.add_argument("--reviewers", nargs="+", default=["alice","bob"], help="Reviewers")
    team_p.add_argument("--quorum", type=int, default=2, help="Quorum")
    team_p.add_argument("--drill", action="store_true", help="Run poison drill instead")

    # swarm claim (Iter 10, C4)
    swarm_p = subparsers.add_parser("swarm-claim", help="Claim a resource for a session")
    swarm_p.add_argument("--repo", required=True, help="Repository path")
    swarm_p.add_argument("--resource", required=True, help="Resource (file)")
    swarm_p.add_argument("--session", required=True, help="Session ID")
    swarm_p.add_argument("--release", action="store_true", help="Release instead of claim")

    # handoff (Iter 10, C4.4)
    handoff_p = subparsers.add_parser("handoff", help="Capture or resume session handoff")
    handoff_p.add_argument("--repo", required=True, help="Repository path")
    handoff_p.add_argument("--session", required=True, help="Session ID")
    handoff_p.add_argument("--decided", nargs="*", default=[], help="Decided items")
    handoff_p.add_argument("--done", nargs="*", default=[], help="Done items")
    handoff_p.add_argument("--blocked", nargs="*", default=[], help="Blocked items")
    handoff_p.add_argument("--resume", action="store_true", help="Resume instead of capture")

    # enforce (Iter 10, C7 ladder)
    enforce_p = subparsers.add_parser("enforce-promote", help="Promote memory up enforcement ladder")
    enforce_p.add_argument("--repo", required=True, help="Repository path")
    enforce_p.add_argument("--id", required=True, type=int, help="Entry ID")
    enforce_p.add_argument("--level", required=True, choices=["context","hook","lint","test","ci"], help="Target level")

    # anchor (Iter 9, C6)
    anchor_p = subparsers.add_parser("anchor", help="Show anchored memories with rename tolerance")
    anchor_p.add_argument("--repo", required=True, help="Repository path")
    anchor_p.add_argument("--file", required=True, help="File path")

    # manifest-watch (Iter 9, C6.2)
    manifest_p = subparsers.add_parser("manifest-watch", help="Flag convention memories whose dependency changed")
    manifest_p.add_argument("--repo", required=True, help="Repository path")

    # hook (Iter 7, C3) - prospective injection, reuses C7 plumbing
    hook_p = subparsers.add_parser("hook", help="Prospective hook (tool-bound injection)")
    hook_p.add_argument("--repo", required=True, help="Repository path")
    hook_p.add_argument("--tool", required=True, help="Tool name")
    hook_p.add_argument("--args-json", default="{}", help="Tool args as JSON")

    # bulk import: one process, one file, N memories (benchmark ingest path).
    # JSONL rows: {"title":..,"content":..,"locator":..,"scope"?}. Secret-blocked
    # rows are skipped and counted (exit 0; summary JSON tells the story).
    import_p = subparsers.add_parser("import-jsonl", help="Bulk import memories from a JSONL file")
    import_p.add_argument("--repo", required=True, help="Repository path")
    import_p.add_argument("--file", required=True, help="JSONL file path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "init":
        result = init_repo(args.path, {"auto_accept": True, "min_commits": args.min_commits})
        print(result["message"])
        sys.exit(0 if result["success"] else 1)

    elif args.command == "install":
        results = install_harness(args.harness)
        for r in results:
            print(f"  {'✅' if r['success'] else '❌'} {r['harness']}: {r['message']}")
        sys.exit(0 if all(r["success"] for r in results) else 1)

    elif args.command == "remember":
        store = get_store(args.repo)
        try:
            entry = store.remember(
                content=args.content,
                surface="text",
                locator=args.file or "",
                scope=args.scope,
                session_id="cli",
            )
        except ValueError as e:
            print(f"❌ Blocked: {e}")
            sys.exit(1)
        print(f"✅ Memory created: {entry['key']}")

    elif args.command == "recall":
        engine = create_recall_engine(args.repo)
        results = engine.recall(query=args.query or "", k=args.limit)
        if getattr(args, "laya_filter", False):
            from kodand.rerank import filter_via_socket

            if not args.query:
                print("❌ --laya-filter requires --query", file=sys.stderr)
                sys.exit(2)
            rows = [
                {"id": e.get("id"), "content": e.get("content", ""),
                 "locator": e.get("locator", ""), "scope": e.get("scope", "repo")}
                for e in results
            ]
            try:
                kept = filter_via_socket(args.query or "", rows, keep_sessions=args.keep)
            except RuntimeError as e:
                print(f"❌ {e}", file=sys.stderr)
                sys.exit(2)
            results = kept
        if getattr(args, "json", False):
            print(json.dumps([
                {"id": e.get("id"), "content": e.get("content", ""),
                 "locator": e.get("locator", ""), "scope": e.get("scope", "repo"),
                 "title": e.get("title", ""),
                 "created_at": e.get("created_at", 0)}
                for e in results
            ]))
        elif not results:
            print("No memories found.")
        else:
            for entry in results:
                print(f"\n📌 {entry.get('title', entry.get('content', '')[:50])}")
                print(f"   {entry.get('content', '')}")
                print(f"   ID: {entry['id']} | Scope: {entry.get('scope', 'repo')}")

    elif args.command == "prospective":
        engine = create_recall_engine(args.repo)
        context = {}
        if args.file:
            context["file_path"] = args.file
        if args.symbol:
            context["symbol"] = args.symbol
        if getattr(args, "cmd", None):
            context["command"] = args.cmd
        results = engine.prospective_recall(context)
        if not results:
            print("No prospective memories found.")
        else:
            for entry in results:
                print(f"\n📌 {entry.get('content', '')[:80]}")
                print(f"   ID: {entry['id']} | Type: {entry.get('memory_type', 'reference')} | Scope: {entry.get('scope', 'repo')}")

    elif args.command == "warm-start":
        ws = create_warm_start(args.repo)
        text = ws.get_warm_context()
        if not text:
            print("No warm start context found. Run `kodand remember` to add entries.")
        else:
            print(text)

    elif args.command == "trust-list":
        ts = TrustSurface(args.repo)
        entries = ts.list()
        if not entries:
            print("No entries found.")
        else:
            for e in entries:
                u = e.get("utility", 0)
                print(f"  #{e['id']} {e['type']} | {e['scope']} | u={u:.1f} | {e['content'][:50]}")

    elif args.command == "trust-inspect":
        ts = TrustSurface(args.repo)
        entry = ts.inspect(args.id)
        if not entry:
            print(f"Entry {args.id} not found.")
        else:
            print(f"ID: {entry['id']}")
            print(f"Content: {entry.get('content', '')}")
            print(f"Locator: {entry.get('locator', '')}")
            print(f"Scope: {entry.get('scope', 'repo')}")
            print(f"State: {entry.get('state', 'active')}")
            print(f"Created: {entry.get('created_at', '')}")

    elif args.command == "trust-correct":
        ts = TrustSurface(args.repo)
        success = ts.correct(args.id, args.kind, args.note)
        if success:
            print(f"✅ Correction filed for entry {args.id}")
        else:
            print(f"❌ Entry {args.id} not found.")

    elif args.command == "trust-delete":
        ts = TrustSurface(args.repo)
        success = ts.delete(args.id)
        if success:
            print(f"✅ Entry {args.id} retired.")
        else:
            print(f"❌ Entry {args.id} not found.")

    elif args.command == "trust-decay":
        ts = TrustSurface(args.repo)
        n = ts.decay(threshold=args.threshold, older_than_days=args.days)
        print(f"Retired {n} low-utility entries (threshold={args.threshold}, older_than={args.days}d)")

    elif args.command == "capture-tick":
        result = run_capture_tick(args.repo)
        print(f"Capture tick: {result['queued']} queued, ceiling: {result['ceiling_hit']}")

    elif args.command == "capture-loop":
        run_capture_loop(args.repo)

    elif args.command == "week":
        from kodand.measure import format_report, north_star_report
        r = north_star_report(args.repo, args.week)
        print(format_report(r))

    elif args.command == "doctor":
        print("🔍 kodand Doctor")
        print()
        print("📦 Installation:")
        harnesses = list_harnesses()
        for h in harnesses:
            print(f"  {'✅' if h['installed'] else '❌'} {h['displayName']}")
        print()
        print("📁 Repository:")
        repo_dir = os.path.join(args.repo, ".kodand")
        if os.path.isdir(repo_dir):
            print(f"  ✅ Initialized: {args.repo}")
        else:
            print("  ❌ Not initialized (run `kodand init`)")
        print()
        print("💾 Database:")
        kodand_dir = os.path.expanduser("~/.kodand")
        if os.path.exists(kodand_dir):
            print("  ✅ ~/.kodand exists")
        else:
            print("  ❌ ~/.kodand not found")
        print()
        print("✅ Doctor check complete")

    elif args.command == "outcome-label":
        scorer = create_outcome_labeler(args.repo)
        success = scorer.label_entry(args.id, args.kind, args.note, holdout=args.holdout)
        if success:
            print(f"✅ Outcome labeled for entry {args.id}")
        else:
            print(f"❌ Entry {args.id} not found.")

    elif args.command == "hook":
        try:
            tool_args = json.loads(args.args_json)
        except Exception:
            tool_args = {}
        hits = before_tool(args.tool, tool_args, args.repo)
        if not hits:
            print("No prospective injection.")
        else:
            for h in hits:
                print(f"[{h['id']}] {h.get('content','')[:120]} -- {h.get('locator','')}")

    elif args.command == "import-jsonl":
        from kodand.store import get_store as _get_store
        store = _get_store(args.repo)
        stored, blocked, errors = 0, 0, 0
        with open(args.file, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    errors += 1
                    continue
                try:
                    store.remember(
                        content=row.get("content", ""),
                        surface="text",
                        locator=row.get("locator", ""),
                        scope=row.get("scope", "repo"),
                        session_id="import-jsonl",
                    )
                    stored += 1
                except ValueError:
                    blocked += 1  # secret/PII filter: skip, count, continue
                except Exception:
                    errors += 1
        print(json.dumps({"stored": stored, "blocked": blocked, "errors": errors}))

    elif args.command == "anchor":
        hits = get_anchored(args.repo, args.file)
        resolved = resolve_anchor(args.repo, args.file)
        if resolved != args.file:
            print(f"Resolved rename: {args.file} -> {resolved}")
        if not hits:
            print(f"No anchored memories for {args.file} (resolved: {resolved})")
        else:
            for h in hits:
                print(f"  #{h['id']} {h.get('memory_type','reference')} | {h.get('locator','')} | {h.get('content','')[:80]}")

    elif args.command == "manifest-watch":
        flags = flag_conventions(args.repo)
        manifests = discover_manifests(args.repo)
        print(f"Manifests: {', '.join([__import__('os').path.relpath(m, args.repo) for m in manifests]) or 'none'}")
        if not flags:
            print("No convention flagged.")
        else:
            for f in flags:
                print(f"  #{f['memory_id']} {f['reason']} -- {f['content']}")

    elif args.command == "team-promote":
        if args.drill:
            r = drill_poison(args.repo)
            print(f"Poison drill blocked={r['blocked']} reason={r['reason']}")
        else:
            if args.id is None:
                print("error: --id required (or use --drill)")
                sys.exit(2)
            r = promote_to_team(args.repo, args.id, args.reviewers, args.quorum)
            print(f"Promote ok={r['ok']} reason={r.get('reason','')}")

    elif args.command == "swarm-claim":
        sw = SwarmCoordination(args.repo)
        if args.release:
            ok = sw.release(args.resource, args.session)
            print(f"Release {args.resource} by {args.session}: {ok}")
        else:
            r = sw.claim(args.resource, args.session)
            print(f"Claim {args.resource} by {args.session}: allowed={r['allowed']} {r.get('reason','')}")

    elif args.command == "handoff":
        ho = Handoff(args.repo)
        if args.resume:
            r = ho.resume(args.session)
            print(f"Resume {args.session}: {r}")
        else:
            r = ho.capture(args.session, decided=args.decided, done=args.done, blocked=args.blocked)
            print(f"Handoff {r['handoff_id']} decided={len(r['decided'])} done={len(r['done'])} blocked={len(r['blocked'])}")

    elif args.command == "enforce-promote":
        en = EnforcementLadder(args.repo)
        ok = en.promote(args.id, args.level)
        print(f"Promote {args.id} -> {args.level}: {ok} now={en.get_enforcement_level(args.id)}")

    elif args.command == "utility":
        scorer = create_utility_scorer(args.repo)
        results = scorer.get_top_entries(args.repo, args.limit)
        if not results:
            print("No entries with utility scores.")
        else:
            for e in results:
                print(f"  #{e['id']} utility={e.get('utility', 0):.2f} | {e.get('content', '')[:60]}")

    elif args.command == "rerank":
        from kodand.rerank import filter_sessions

        if args.repo:
            engine = create_recall_engine(args.repo)
            results = engine.recall(query=args.query, k=args.limit)
            chunks = [
                {"id": e.get("id"), "content": e.get("content", ""),
                 "locator": e.get("locator", ""), "scope": e.get("scope", "repo")}
                for e in results
            ]
        else:
            chunks = json.load(sys.stdin)
        try:
            kept = filter_sessions(
                args.query, chunks, keep_sessions=args.keep, model_path=args.model
            )
        except RuntimeError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(kept))

    elif args.command == "rerank-server":
        from kodand.rerank import serve

        serve(model_path=args.model)

    elif args.command == "fetch-model":
        from kodand.fetch_model import default_dest, fetch

        try:
            status = fetch(Path(args.dest) if args.dest else default_dest())
        except RuntimeError as e:
            print(f"❌ fetch-model: {e}", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(status))

    elif args.command == "ingest-artifact":
        from kodand.artifacts import ingest_artifact

        store = get_store(args.repo)
        try:
            status = ingest_artifact(store, args.repo, args.path, caption=args.caption or "")
        except (RuntimeError, FileNotFoundError) as e:
            print(f"❌ ingest-artifact: {e}", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(status))

    elif args.command == "assemble":
        from kodand.assemble import assemble
        from kodand.recall import create_recall_engine

        engine = create_recall_engine(args.repo)
        results = engine.recall(query=args.query, k=args.limit * 3)
        rows = [{"sessionId": (e.get("locator") or "-").split("#")[0],
                 "entryId": e.get("id"),
                 "content": e.get("content", ""),
                 "session_p": None}
                for e in results]
        prefix = Path(args.prefix_file).read_text(encoding="utf-8")
        try:
            out = assemble(prefix, rows, args.query,
                           state_path=Path(args.state_file),
                           kill_switch=os.environ.get("KODAND_BASELINE") == "1",
                           max_blocks=args.limit)
        except RuntimeError as e:
            print(f"❌ assemble: {e}", file=sys.stderr)
            sys.exit(3)
        print(json.dumps(out))

    elif args.command == "memory-surface":
        from kodand.surface import serve

        server, _svc, url = serve(args.repo, port=args.port, host=args.host)
        print(f"memory surface: {url}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

    elif args.command == "rerank-serve":
        from kodand.rerank import serve_tcp

        serve_tcp(args.host, args.port, model_path=args.model)

    elif args.command == "recalld":
        from kodand.recalld import serve_tcp

        serve_tcp(args.host, args.port)


if __name__ == "__main__":
    main()