# G1 — Week 1 Dogfooding (2026-W43)

**Repo:** kodand (this repo) + stranger Docker `kodand-stranger-test`
**Window:** 2026-10-19 .. 2026-10-26 (W43)
**Counters live:** Tranche 0 spine (re-explanation, repeated-mistake, events, cost) + 1.1 capture loop (ceiling 5/day)
**Gate:** week2 < week1 on both north-star numbers (repeated-mistake rate + re-explanation count), all 1.x bars hold, stranger keeps it installed. Numbers recorded either way.

## Daily log

| Day | Captured | Provenance | Notes |
|-----|----------|------------|-------|
| 2026-10-19 | - | init | G1 start, north-star baseline |

## North-star baseline (start of week)

```
week 2026-W43 (2026-10-19 .. 2026-10-26)
repeated-mistake count : 0
outcome events         : 0
repeated-mistake rate  : n/a (no outcome events in week)
re-explanation count   : 0
captured               : 0
blocked                : 0
held                   : 0
validated              : 0
retired                : 0
```

## Stranger week (parallel)

Image: `kodand-stranger-test` (fresh `pip install /opt/workspace`, 100% local, 676G HDD).
Run: `docker run --rm kodand-stranger-test bash /opt/workspace/stranger-test.sh`

## How to log

```bash
kodand capture-tick --repo .   # daily, ceiling 5/day
kodand week --repo .           # check north-star
kodand trust-list --repo .     # review queue
```
