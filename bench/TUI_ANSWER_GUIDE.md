# TUI Answer Harness — use any opencode session/model on same retrieval

You said: keep good Hit (0.81) and only fix stuck numbers, plus answers depend on model reasoning. This decouples them.

## Already dumped (6.9 MB, 500 Q, Hit frozen)

```
bench/retrieval-dump/full500-hcil.json  # from full500-hcil report.json, 500 Q, 11 results each, hierarchical summaries at top
```

Created via:
```
node scripts/dump-search.mjs --runId full500-hcil
# also works after search-only: bun run src/index.ts run -p kodand -b longmemeval -r <runId> -f search → then dump
```

## How to answer from TUI (no re-index, same Hit)

**In this TUI (Muse Spark 1.3) run:**
```
node scripts/answer-dump.mjs --dump bench/retrieval-dump/full500-hcil.json --model opencode-go/muse-spark-1.3-contributor --out bench/answers/full500-hcil-spark.json
# This will try opencode headless; if it hangs (gateway 1010), do manual:
# The script falls back to nvidia for headless, but for TUI you should do:
```
Manual TUI (guaranteed, no gateway hang):
1. `read bench/retrieval-dump/full500-hcil.json` (first 2 Q to see shape)
2. For each Q, prompt concisely: `Context:\n<searchResults[0..9].content>\nQuestion: <question>\nAnswer:`
3. Write `bench/answers/full500-hcil-tui.json` as `[{questionId, question, groundTruth, hypothesis, answeringModel:"opencode-tui"}]`

I can do this for you now on a 20Q slice to prove: `bench/retrieval-dump/adv30-hcil6.json` (same method, 20 Q, adv30 hardest).

**In another opencode session/model (e.g., Nemotron) run:**
```
node scripts/answer-dump.mjs --dump bench/retrieval-dump/full500-hcil.json --model nvidia/nemotron-3.5-lightning-30b-a3b --out bench/answers/full500-hcil-nemotron2.json
```

## Evaluate same retrieval, different reasoning

```
node scripts/evaluate-dump.mjs --answers bench/answers/full500-hcil-spark.json --judge nvidia/nemotron-3.5-lightning-30b-a3b
node scripts/evaluate-dump.mjs --answers bench/answers/full500-hcil-nemotron2.json --judge nvidia/nemotron-3.5-lightning-30b-a3b
# Both use same searchResults, same judge, so accuracy delta is pure reasoning, Hit unchanged 0.81
```

## What to improve next (only stuck numbers)

Not whole setup — keep `Hit 0.81` (good). Stuck:
- `preference 30% 9/30 Hit 0.63 MRR 0.42` → needs `I5` profile cache (one extra `recall "preferences"`), not Hit
- `multi 36% 48/133` → needs `COUNT` synth already proven `adv30-hcil6 4/20` (+1), keep it as ledger intent
- `knowledge 71.8% vs 75.6%` → `MRR 0.49 vs 0.74` ranking drop, fix re-rank not extra slots

All dumps/answers are git-ignored, `report.json` stays source of truth.
