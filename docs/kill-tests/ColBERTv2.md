# Kill-test: ColBERTv2 late interaction

**What it is (authoritative):** `arxiv:2112.01488` — per-token multi-vector + residual compression (centroid + quantized residual), 6-10× compression vs ColBERT, state-of-art on BEIR/MS MARCO.

**Why it might help kodand:** `MRR 0.574` mid-pack; late interaction could push `MRR 0.57→0.70` offline without RAG LLM.

**Kill criteria:** If needs per-token embeddings (avg 100 tokens × 128 dim × 2 bytes ≈ 640MB for 25k chunks) + k-means codebook + decompress per query → KILL on 5.7Gi box with `bge-reranker` already 105M. Also KILL if GPU required for encoding.

**Verdict so far:** KILL for P0 — same `MRR` gain as `bge-reranker` + `FTS15+aggregation` but 10× index size and residual decompress per query. Keep `bge-reranker` (single vector, already cached) as `I2`, not ColBERTv2.

**Scale note:** Jina-ColBERT-v2 best at 25KB/doc down to 64 dims, but still multi-vector per token — overkill at 25k docs where `Hit 75%` is aggregation, not ranking.
