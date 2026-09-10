"""
Retrieval evaluation against a golden set.

A golden item names a mentor, a student-style query, and phrases that a
relevant passage would contain. A retrieved list "hits" when any returned
chunk contains any expected phrase (case-insensitive). From that we report:

  recall@k  fraction of queries with at least one hit in the top k
  MRR       mean of 1/rank of the first hit (0 when none), rewards ranking
            the relevant passage near the top, not just somewhere in the k

Phrase matching is a pragmatic relevance judgement: it needs no hand-labelled
chunk ids, survives re-chunking, and is easy to extend. Its weakness is that a
passage can be relevant without the exact phrase; keep several phrases per
item to soften that.
"""

from typing import Any


def _first_hit_rank(chunks: list[str], phrases: list[str]) -> int | None:
    wanted = [p.lower() for p in phrases]
    for rank, chunk in enumerate(chunks, 1):
        low = chunk.lower()
        if any(p in low for p in wanted):
            return rank
    return None


def evaluate_retrieval(golden: list[dict[str, Any]], results: dict[str, list[str]], k: int) -> dict[str, Any]:
    """
    golden:  [{"mentor_id", "query", "expect_any": [phrases]}]
    results: query -> list of returned chunk texts (ranked)
    """
    per_query = []
    hits = 0
    rr_sum = 0.0
    for item in golden:
        chunks = results.get(item["query"], [])[:k]
        rank = _first_hit_rank(chunks, item["expect_any"])
        hit = rank is not None
        hits += hit
        rr_sum += (1.0 / rank) if rank else 0.0
        per_query.append({"mentor_id": item["mentor_id"], "query": item["query"], "hit": hit, "rank": rank})
    n = len(golden)
    return {
        "k": k,
        "n": n,
        "recall_at_k": (hits / n) if n else 0.0,
        "mrr": (rr_sum / n) if n else 0.0,
        "misses": [q for q in per_query if not q["hit"]],
        "per_query": per_query,
    }
