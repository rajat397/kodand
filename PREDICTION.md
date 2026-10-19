# PREDICTION.md — Iteration 1 (Tranche 0 + 1.1)

**Session:** Iteration 1 — Foundation & Live Capture Loop  
**Date:** 2026-10-19  
**Tranche:** 0 (Measurement Spine) + 1.1 (Live Capture Loop)

---

## Pre-Registered Acceptance Criteria

| ID | Criterion | Target | Measurement Method |
|----|-----------|--------|-------------------|
| A0.1 | Re-explanation counter detects human re-stating known decision/constraint | ≥ 90% recall on planted fixtures | `kodand measure reexplain --fixture fixtures/reexplain.jsonl` |
| A0.2 | Repeated-mistake counter detects agent repeating corrected mistake | ≥ 90% recall on planted fixtures | `kodand measure mistake --fixture fixtures/mistake.jsonl` |
| A0.3 | Capture/recall event log captures every event with provenance | 100% of captures/injections/outcomes logged | `kodand measure events --verify` |
| A0.4 | Cost log records tokens/latency per mechanism per session | 100% of mechanisms logged | `kodand measure cost --verify` |
| A0.5 | North-star numbers computable from logs for any week | `kodand week --repo .` outputs both numbers | `kodand week --repo . --verify` |
| A1.1 | Live capture precision ≥ 0.70 (calibrated bar) | Precision ≥ 0.70 on planted fixtures | `kodand capture test --fixture fixtures/capture.jsonl` |
| A1.2 | Explicit "remember this" commands ≈ 0 across a week | ≤ 1 per week in live dogfooding | Manual count |
| A1.3 | Review queue ≤ ceiling (5/day) | Queue never exceeds ceiling | `kodand capture status` |
| A1.4 | North-star numbers computable from logs for any week | `kodand week --repo .` outputs both numbers | `kodand week --repo . --verify` |

---

## Pre-Registered Kill Signals

| Signal | Action |
|--------|--------|
| Capture precision < 0.70 after 2 tuning passes | Rethink capture source, not thresholds |
| Explicit "remember this" > 2/week | Add more capture signals |
| Review queue consistently hits ceiling | Increase ceiling or improve precision |
| North-star numbers not computable from logs | Fix log schema |

---

## Pre-Registered Null Hypotheses (Counterfactuals)

| Null Hypothesis | Test |
|-----------------|------|
| H0: Re-explanation counter cannot distinguish re-explanation from new info | Precision < 50% on held-out fixtures |
| H0: Repeated-mistake counter fires on novel mistakes | False positive rate > 10% on novel mistakes |
| H0: Live capture loop produces no more signal than random | Precision ≤ random baseline (0.10) |
| H0: Explicit "remember this" commands remain high | > 5/week in live dogfooding |

---

## Pre-Registered Fixes (If Null Not Rejected)

| Null Not Rejected | Pre-Registered Fix |
|-------------------|-------------------|
| Re-explanation precision low | Add more context (surrounding turns, file context) |
| Repeated-mistake false positives high | Require exact signature match + test failure |
| Live capture precision low | Add more capture signals (CI logs, PR comments, revert commits) |
| Explicit "remember this" high | Add more automatic capture signals |

---

## Measurement Plan

| Metric | Tool | Frequency |
|--------|------|-----------|
| Re-explanation precision/recall | `kodand measure reexplain --fixture` | Per commit |
| Repeated-mistake precision/recall | `kodand measure mistake --fixture` | Per commit |
| Capture precision | `kodand capture test --fixture` | Per commit |
| North-star numbers | `kodand week --repo .` | Weekly |
| Cost per mechanism | `kodand measure cost --summary` | Per session |

---

## Sign-Off

**Pre-registered by:** Orchestrator  
**Date:** 2026-10-19  
**Status:** PRE-REGISTERED — No changes after implementation begins
