# Retrieval dump → TUI answer harness

Decouples **index+search (our HCIL Hit/MRR)** from **answer reasoning (model)** so we improve only stuck numbers, not reject the whole setup.

## Flow

```
bun run src/index.ts run -p kodand -b longmemeval -r <runId> -f search   # ingest+index+search only, 500 containers, Hit/MRR frozen
bun run dump-search --runId <runId>                                        # exports checkpoint.searchResults → bench/retrieval-dump/<runId>.json
# Now any opencode TUI / model can answer the SAME retrieval
bun run answer-dump --dump bench/retrieval-dump/<runId>.json --model <model> --out bench/answers/<runId>-<model>.json
bun run evaluate-dump --answers bench/answers/<runId>-<model>.json --judge <judge>  # same judge as full500
```

`dump` is `[{questionId, question, groundTruth, questionType, searchResults: [{sessionId, content, locator}]}]` — no answers, just retrieval.

## Why this helps

- **Good Hit stays:** `full500-hcil Hit 0.81` is kept, we don't re-ingest. Only weak `byType` (preference 0.30, multi 36%) get targeted fixes, then re-dump.
- **Model reasoning isolated:** same dump answered by `nvidia/lightning` (harness) vs `opencode-go/muse-spark-1.3-contributor` (TUI) vs `nvidia/nemotron` — see if accuracy lifts from reasoning alone, Hit unchanged.
- **Fast iteration:** `dump` is 7M JSON, `answer-dump` is 500× LLM calls, no 23867-episode re-index.

## TUI usage

In opencode TUI (this repo):

```
# 1. Dump after search (already done for full500-hcil)
bun run dump-search --runId full500-hcil

# 2. Answer in TUI with Spark (you)
bun run answer-dump --dump bench/retrieval-dump/full500-hcil.json --model opencode-go/muse-spark-1.3-contributor --out bench/answers/full500-hcil-spark.json

# 3. Answer in another session/model (e.g., Nemotron) for compare
bun run answer-dump --dump bench/retrieval-dump/full500-hcil.json --model nvidia/nemotron-3.5-lightning-30b-a3b --out bench/answers/full500-hcil-nemotron.json

# 4. Evaluate both with same judge
bun run evaluate-dump --answers bench/answers/full500-hcil-spark.json --judge nvidia/nemotron-3.5-lightning-30b-a3b
```

All `dump`/`answers` are git-ignored, `checkpoint.json` is source of truth.
