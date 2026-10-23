# Kill-test: ColBERTv2 late interaction

**What it is (authoritative):** `arxiv:2112.01488` — per-token multi-vector + residual compression (centroid + quantized residual), 6-10× compression vs ColBERT, state-of-art on BEIR/MS MARCO.

**Why it might help kodand:** `MRR 0.574` mid-pack; late interaction could push `MRR 0.57→0.70` offline without RAG LLM.

**Kill criteria:** If needs per-token embeddings (avg 100 tokens × 128 dim × 2 bytes ≈ 640MB for 25k chunks) + k-means codebook + decompress per query → KILL on 5.7Gi box with `bge-reranker` already 105M. Also KILL if GPU required for encoding.

**Verdict so far:** DEFER to P1 — same `MRR` gain as `bge-reranker` for P0, but **late interaction is the large-scale answer** (`6-10×` residual compression, denoised supervision, multi-vector per token). At `2.5M` chunks, `bge-reranker` single-vector saturates; `ColBERTv2`'s token-level `HNSW` is the `sub-300ms` path for `largest repos`. Keep `bge-reranker` (105M cached) for P0, `ColBERTv2` as `P1` for `HNSW vs IVF` bake-off at scale.

**Scale note:** Jina-ColBERT-v2 best at 25KB/doc down to 64 dims, but still multi-vector per token — overkill at 25k docs where `Hit 75%` is aggregation, not ranking.
