# Laya as DecisionRAG judge — Gate 1 result

Date: 2026-10-30
Checkpoint: `convaiinnovations/laya` multilingual (mmBERT-base, 322M, 615 MB safetensors, max_len 8192)
Runtime: `laya==0.4.17`, torch CPU, 2-core Ryzen 3 3250U. Load 28 s, steady RSS ~1.3 GB.
Task: score `kodand recall` chunks for a LongMemEval question, then session-level evidence recall@10.

## Verdict

Zero-shot Laya does not separate gold from non-gold. Every framing tried produced
scores that were saturated, near-uniform, or ordered below a non-gold passage.
This matches Laya's own model card: base English checkpoint 0.362 accuracy
zero-shot vs 0.766 fine-tuned. The paper's gains come from a *task-trained*
judge; an untrained decision head does not reproduce them.

## Measurements

Question `06f04340` (preference; gold session best chunk at baseline rank 29):

| framing | result |
|---|---|
| shared context, 4 passages, noul | 0.444 / 0.486 / 0.520 / 0.472 — no separation |
| shared context, 4 passages, choice | 0.887 yes for all — saturated |
| single passage, noul, 30 chunks | 124 s; gold rank 29 -> 13 |
| single passage, noul, batched bs=8, 30 chunks | 58 s; gold rank 29 -> 13 |
| noul at 300 / 500 / 700 chars | gold 0.371 / 0.378 / 0.684; non-gold 0.676 constant |
| choice over 8 passages | near-uniform 0.088–0.164; gold 0.143 vs top 0.164 |
| score rubric (3 levels) | near-uniform; gold not top |

Phrasing/order sweep, 500 chars, gold vs the same non-gold passage:

| statement | gold | non-gold |
|---|---|---|
| "The passage answers the question." (passage first) | 0.625 | 0.681 |
| "...contains a concrete suggestion..." (passage first) | 0.711 | 0.715 |
| "...directly answers..." (question first) | 0.312 | 0.398 |
| "...is useful for answering..." (passage first) | 0.596 | 0.653 |

Gold lost to the same non-gold passage in all four framings.

Other questions: `4adc0475` gold rank 12 -> 7 (hit); `09d032c9` gold absent
from top-30 (baseline rank 31, so the pool, not the judge, was the limit).

## Cost

30 candidates: 58–124 s CPU. 60 candidates: ~2 min+. 20 questions: ~40 min per pass.

## What this rules out

- Laya zero-shot as a drop-in relevance judge, in any of noul / choice / score,
  shared-context or pointwise.
- Treating the paper's reported gains as reproducible without training the judge.

## Only remaining path on this hardware

Fine-tune Laya's 2-layer decision head with the encoder frozen, using cached
encoder states. Head training is minutes; the cost is the forward passes
(~1.5 s each on CPU). A 200-question x 6-candidate disjoint subset is ~30 min of
forwards. Risk: session-level labels are noisy at chunk level, and adv30/holdout30
must be excluded from training to keep the gate honest.

---

# Correction (same day): the formulation was the bug

The gate above put the question in the *state* (`Question: Q\n\nPassage: P`)
with a generic instruction. Laya reads the question-end marker, so the decision
head never saw the question. Moving Q into the instruction fixes it:

- state: `Passage: <chunk>`
- noul instruction: `This passage would help answer the question: <Q>`

## Result on the 20 `adv30-hybrid-fixed` questions (top-30 chunk pool)

| rule | any gold | all gold | avg session recall | kept |
|---|---|---|---|---|
| baseline (raw recall order, top-10 chunks) | 13/20 | 8/20 | 0.520 | 10.0 |
| session-dedup only, top-10 sessions | 15/20 | 9/20 | 0.630 | 9.7 |
| absolute P >= 0.3 | 13/20 | 6/20 | 0.505 | 5.5 |
| absolute P >= 0.5 | 12/20 | 6/20 | 0.458 | 3.7 |
| **Laya top-8 sessions, 1 chunk each** | **16/20** | **11/20** | **0.718** | **8.0** |
| Laya top-10 sessions, 1 chunk each | 16/20 | 13/20 | 0.755 | 9.7 |
| Laya top-15 chunks | 16/20 | 12/20 | 0.730 | 15.0 |

Reading:

- Absolute thresholds are worse than baseline: P is not calibrated across
  questions (a gold chunk on `4adc0475` scores 0.353 while a non-gold chunk on
  `2788b940` scores 0.095). Only the within-question order carries signal.
- Session dedup alone is worth +0.110 recall; Laya ordering adds another
  +0.088 on top at the same budget (8 sessions vs 10 chunks).
- +0.198 absolute over baseline with 2 fewer items (20% fewer chunks fed to the answer model).
- Per-question spread is still uneven: `06f04340` gold lands at rank 7,
  `95228167` has no gold chunk in the top-30 pool at all (retriever limit, not
  the judge).

## Cost

~55 s per question for 30 candidates, plus ~28 s model load. Full 20-question
pass ~40 min on this CPU. Batched scoring and a persistent process are the
obvious next optimizations.

## Status

Zero-shot Laya **works as a relative reranker**, not as an absolute filter.
Wired as `kodand rerank` (`kodand/rerank.py`) and enabled in the memorybench
kodand provider with `KODAND_LAYA_RERANK=1` (keep count via `KODAND_LAYA_KEEP`,
default 8).
