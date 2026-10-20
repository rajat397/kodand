# Benchmark report — repeated-mistake rate, v4 conflict protocol (2026-10-20)

## Protocol (pre-registered in IMPLEMENTATION-PLAN.md + tasks32.json v4)
- 32 tasks × 4 arms × 3 runs = **384 fresh-session runs**, task-major order.
- Retest explicitly requests the anti-pattern (grader literal); the prior-session
  correction must override the new request. Grader = deterministic grep, no LLM judge.
- Arms: `no-memory` | `agents-md` (AGENTS.md advisory) | `kodand-inject` (memory text)
  | `kodand-enforce` (memory + generated blocking test + grader available).
- Model: `ollama/qwen2.5:1.5b` local, temp 0, pinned per row. (Substitution documented:
  headless `opencode run` streams hang on all providers — streams start, zero tokens,
  env/plugins/network ruled out. Harness is model-agnostic; re-run to upgrade.)
- Pre-registered bar: kodand-enforce repetition < best advisory arm by **≥15pp**.
- Primary metric: repetition over ALL runs (abstentions count as HELD).
  Secondary: repetition over COMPLETED runs only (agent changed the file).

## Results (n=96/arm)

| arm | primary rep / n | rate [95% CI] | completed-only rep / n | rate [95% CI] |
|---|---|---|---|---|
| no-memory | 50/96 | 0.521 [0.422, 0.618] | 50/56 | 0.893 [0.785, 0.950] |
| agents-md | 57/96 | 0.594 [0.494, 0.687] | 57/60 | 0.950 [0.863, 0.983] |
| kodand-inject | 45/96 | 0.469 [0.372, 0.568] | 45/67 | 0.672 [0.553, 0.772] |
| kodand-enforce | 39/96 | 0.406 [0.313, 0.506] | 39/61 | 0.639 [0.514, 0.748] |

## Verdict (reported, not spun)
- **Primary bar NOT met**: enforce (0.406) vs best advisory no-memory (0.521) = **11.5pp**,
  CIs overlap substantially. The 15pp margin fails on the primary metric.
- **Completed-only: significant**: enforce 0.639 vs no-memory 0.893 = **25pp**, CIs do not
  overlap ([0.514,0.748] vs [0.785,0.950]). When agents act, memory cuts repetition.
- **Advisory context = nothing**: agents-md completed-only 0.950 vs no-memory 0.893 —
  AGENTS.md does not override a direct request (matches ETH Zurich ceiling thesis).
- **Inject vs enforce: no separation** (0.469 vs 0.406 primary, overlapping CIs). The
  enforcement ladder adds little over inject on this model/task set — negative result,
  kept. Mechanism trace shows why: agents often never run the generated test; and when
  they do see FAIL (wildcard-1: grader FAIL observed by agent), the 1.5b model still
  ships the mistake. Enforcement needs a forcing function, not an optional check.

## Per-category repetition (rep/n: no-mem / agents / inject / enforce)
- bare-except: 11 / 11 / 1 / 4 — memory works.
- open-encoding: 3 / 3 / 0 / 0 — memory perfect.
- print-debug: 8 / 10 / 9 / 4 — enforce halves it, inject does not.
- mutable-default: 11 / 11 / 6 / 6 — halves it.
- sleep-retry: 0 / 0 / 3 / 3 — model never makes this mistake unprompted; kodand arms
  introduce noise here (abstention + occasional compliance with prompt over memory).
- assert-prod: 0 / 0 / 5 / 1 — same floor pattern; enforce best.
- wildcard: 10 / 10 / 12 / 12 — **universal failure**: every arm repeats, memory ignored.
- hardcoded: 7 / 12 / 9 / 9 — memory does not help; advisory hurts.

## Limitations (do not cite beyond these)
1. Weak local model (1.5b): absolute rates reflect model obedience, not just memory.
   Re-run the same harness on a frontier model before product claims.
2. v4 retests are adversarial by design (explicit anti-pattern request). This measures
   correction-override strength — the intent — not ambient mistake rates.
3. No human study, no second harness, single session-date. Transcripts: `transcripts_v4/`.
4. 3 model arms (native-auto/mem0/claude-mem) skipped openly — requirements absent.

## Reproduce
`python3 runner/agent_loop.py --tasks 32 --runs 3 --tag v4 --model <ollama-id> --resume`
then `python3 score.py results_agent_v4.jsonl`. Raw rows: `results_agent_v4.jsonl`.
