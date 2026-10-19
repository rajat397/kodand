# Kodand — Launch Checklist (one-command install, 100% local)

**Goal:** `pip install kodand` → `kodand init` → `kodand install <harness>` works on a clean machine, no cloud, no accounts.

## Pre-launch verification (clean Docker `python:3.11-slim`)

| # | Check | Command | Expected | Status |
|---|-------|---------|----------|--------|
| 1 | Install | `pip install /opt/workspace` | `kodand --help` shows 23 commands | ☐ |
| 2 | Init | `kodand init . --min-commits 0` | `Initialized kodand for ...` | ☐ |
| 3 | Remember | `kodand remember --repo . --title "T" --content "C" --file "f.py"` | `✅ Memory created: N` + auto `captured` event | ☐ |
| 4 | Recall | `kodand recall --repo . --query "C"` | Returns #N | ☐ |
| 5 | Prospective | `kodand hook --repo . --tool write --args-json '{"file_path":"f.py"}'` | Injects matching entry, capped 3, never blocks | ☐ |
| 6 | Warm-start | `kodand warm-start --repo .` | Shows recent decisions/corrections, re-appended every turn | ☐ |
| 7 | Trust list | `kodand trust-list --repo .` | Shows `u=` utility, sorted by utility | ☐ |
| 8 | Trust correct | `kodand trust-correct --repo . --id N --kind false_hold --note "x"` | `✅ Correction filed`, logs `corrected` | ☐ |
| 9 | Trust decay | `kodand trust-decay --repo . --threshold 0.0 --days 0` | Retires low-utility, logs `retired` | ☐ |
| 10 | Capture | `kodand capture-tick --repo .` | `queued` respects ceiling 5/day, cursor prevents re-mine | ☐ |
| 11 | Anchor | `kodand anchor --repo . --file "f.py"` | Rename tolerance via `git log --name-status --diff-filter=R` | ☐ |
| 12 | Manifest | `kodand manifest-watch --repo .` | Flags convention on `express 4->5` change | ☐ |
| 13 | Team | `kodand team-promote --repo . --drill` → blocked, `--id N --reviewers alice bob` → ok | Poison blocked, quorum required | ☐ |
| 14 | Swarm | `kodand swarm-claim --repo . --resource f --session s1` → allowed, s2 → denied | Deny-and-propose, persistent `.kodand/claims.json` | ☐ |
| 15 | Handoff | `kodand handoff --repo . --session s1 --decided "d" --resume` | Ledger `decided/done/blocked` | ☐ |
| 16 | Enforce | `kodand enforce-promote --repo . --id N --level hook` | `hook`→`ci` migration adds column if missing | ☐ |
| 17 | Week | `kodand week --repo .` | `captured/blocked/held/validated/retired/re-explanation/repeated` from logs alone | ☐ |
| 18 | Outcome/Utility | `kodand outcome-label --repo . --id N --kind avoided_mistake` → `kodand utility --repo .` | `utility` drives recall rank | ☐ |
| 19 | Doctor | `kodand doctor --repo .` | Shows harness + repo + DB | ☐ |
| 20 | Secret/PII | `kodand remember --content "sk-..."` → blocked | `❌ Blocked: secret detected` | ☐ |
| 21 | Uninstall | `kodand uninstall all` + `pip uninstall kodand` | `UNINSTALLED`, DB remains until `rm -rf ~/.kodand` | ☐ |
| 22 | No network | `lsof -i` inside container → no outbound | Zero network after `pip install` | ☐ |

## How to run the checklist (Docker, HDD)

```bash
# Build once (HDD, 676G)
docker build -t kodand-launch-check -f /home/rajat/kodand-docker-ctx/Dockerfile /home/rajat/kodand-docker-ctx

# Run checklist in fresh container (no prior ~/.config, no marker)
docker run --rm kodand-launch-check bash /opt/workspace/LAUNCH_CHECKLIST.sh
```

