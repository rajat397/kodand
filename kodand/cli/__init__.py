"""
kodand.cli - Command-line interface for kodand
"""

import sys
import argparse
import os
from kodand.store import get_store
from kodand.capture import run_capture_tick, CaptureLoop
from kodand.recall import create_recall_engine, recall
from kodand.trust import TrustSurface
from kodand.hooks import before_tool
from kodand.warmstart import create_warm_start, get_warm_context
from kodand.anchor import get_anchored, resolve_anchor
from kodand.manifest import flag_conventions, discover_manifests
from kodand.install import install_harness, uninstall_harness, list_harnesses, init_repo
from kodand.outcome import create_outcome_labeler
from kodand.utility import create_utility_scorer


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

    # utility
    utility_p = subparsers.add_parser("utility", help="Show utility scores")
    utility_p.add_argument("--repo", required=True, help="Repository path")
    utility_p.add_argument("--limit", type=int, default=10, help="Maximum results")

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
        entry = store.remember(
            content=args.content,
            surface="text",
            locator=args.file or "",
            scope=args.scope,
            session_id="cli",
        )
        print(f"✅ Memory created: {entry['key']}")

    elif args.command == "recall":
        engine = create_recall_engine(args.repo)
        results = engine.recall(query=args.query or "", k=args.limit)
        if not results:
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
        from kodand.measure import north_star_report, format_report
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
        success = scorer.label_entry(args.id, args.kind, args.note)
        if success:
            print(f"✅ Outcome labeled for entry {args.id}")
        else:
            print(f"❌ Entry {args.id} not found.")

    elif args.command == "hook":
        import json
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

    elif args.command == "utility":
        scorer = create_utility_scorer(args.repo)
        results = scorer.get_top_entries(args.repo, args.limit)
        if not results:
            print("No entries with utility scores.")
        else:
            for e in results:
                print(f"  #{e['id']} utility={e.get('utility', 0):.2f} | {e.get('content', '')[:60]}")


if __name__ == "__main__":
    main()