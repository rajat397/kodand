# Tranche 0 — Measurement Spine (Detailed Design)

**Goal:** Without counters, the north star cannot be reported and gates cannot be judged.
**Size:** S (1 session)
**C-lines:** C1, C2, C5, C8

## Why this tranche first
Every gate (G1-G5) is judged on `repeated-mistake rate` and `re-explanation count`. Without a
measurement spine, we cannot tell if we are improving or gaming the metric. This tranche
exists to make the north star computable from logs alone for any user and any week.

## Pre-registered acceptance (ANTI-GAMING)

| ID | Criterion | Target | How measured |
|----|-----------|--------|--------------|
| A0.1 | Re-explanation counter detects human re-stating decision/constraint already in record | ≥90% recall, ≤10% FP on planted fixtures | `fixtures/reexplain.jsonl` — 50 re-explanations + 50 novel statements on podman history |
| A0.2 | Repeated-mistake counter detects agent repeating corrected mistake | ≥90% recall, ≤10% FP | `fixtures/mistake.jsonl` — 50 repeated mistakes + 50 novel mistakes on podman |
| A0.3 | Capture/recall event log | 100% of captures/injections/outcomes logged with provenance | `kodand measure events --verify` — check every event has ts/kind/entry_id/provenance |
| A0.4 | Cost log | 100% of mechanisms logged | `kodand measure cost --verify` — every capture/recall/warmstart/prospective logs tokens/latency/model |
| A0.5 | North-star numbers from logs alone | `kodand week --repo .` outputs both numbers for any ISO week, computed solely from logs | `kodand week --repo . --verify` — start/end timestamps, rate = repeated/outcome else n/a |

## Design

### 0.1 Re-explanation counter
```python
# packages/core/src/measure/reexplanation.ts
# Input: user utterance + surrounding 5 turns + file context
# Output: {isReexplanation: bool, matchedEntryId, similarity: 0.75}
# Algorithm: Jaccard on tokenized content (stopwords removed, len>2), threshold 0.75
# + re-explanation marker heuristic: "we already...", "as I said", "remember we..."
# + high content overlap (>0.4) + marker => re-explanation
# Logged as kind=reexplanation, ts, entry_id, provenance, detail={similarity, context}
```

### 0.2 Repeated-mistake counter
```python
# packages/core/src/measure/repeatedMistake.ts
# Input: agent action (tool, file, symbol, code) + outcome (success, error, errorType)
# Output: {isRepeated: bool, originalMistakeId, severity}
# Algorithm: generate signature = hash(tool|file|symbol|errorType), search correction memories (type=correction, last 30d)
# + Jaccard similarity >0.7 + severity mapping (security→critical, crash→critical, test fail→high)
# Logged as kind=repeated_mistake, ts, entry_id
```

### 0.3 Event log
```typescript
// packages/core/src/measure/eventsLog.ts
type EventKind = 'captured'|'injected'|'outcome'|'reexplanation'|'repeated_mistake'|'cost'|'warmstart'|'prospective';
interface Event { ts: string, kind: EventKind, entry_id?: number, provenance: string, detail?: string }
class EventLogger { buffer: Event[], flush(size=10, interval=5s), log(event: Partial<Event>) }
// Logged to .kodand/events.log (JSONL) + SQLite events table
```

### 0.4 Cost log
```typescript
// packages/core/src/measure/costLog.ts
interface CostRecord { mechanism: 'capture'|'recall'|'warmstart'|'prospective'|'trust'|'parser', tokensIn, tokensOut, tokensReasoning, latencyMs, model, success }
class CostLogger { log(record: Omit<CostRecord, 'id'|'timestamp'>) }
// Logged to .kodand/cost.log
```

### Week report
```typescript
// packages/core/src/measure/weekReport.ts
// week = ISO YYYY-Www, start = Monday 00:00, end = start+7d
// repeated-mistake rate = repeated_mistakes / outcome_events else "n/a"
// re-explanation count = reexplanation events in week
// from logs alone: eventsLog + costLog for the week
```

## Real-world repo: containers/podman (Red Hat)
- Large Go monorepo, 10k+ commits, good for 0.1/0.2 fixtures
- HDD: /mnt/data/docker-kodand/podman (shallow → full clone)
- Docker: python:3.11-slim, git, fresh ~/.kodand, test via fixtures

## Kill signals
- Re-explanation precision <90% after 2 passes → add file context + surrounding turns
- Repeated-mistake FP >10% → require exact signature + test failure

## Files
```
packages/core/src/measure/
  reexplanation.ts, repeatedMistake.ts, eventsLog.ts, costLog.ts, weekReport.ts, index.ts
  fixtures/reexplain.jsonl, fixtures/mistake.jsonl (50+50 each, from podman)
packages/storage/src/sqlite/ — events, cost tables
packages/cli/src/measure.ts — kodand measure week|reexplain|mistake|events|cost
```

## Verification
```bash
kodand measure reexplain --fixture fixtures/reexplain.jsonl  # expect ≥90% / ≤10%
kodand measure mistake --fixture fixtures/mistake.jsonl
kodand measure events --verify && kodand measure cost --verify
kodand week --repo /mnt/data/docker-kodand/podman --verify
```
