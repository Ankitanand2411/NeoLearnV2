"""
Run the golden-set retrieval evaluation against the live database.

    python scripts/eval_retrieval.py                 # hybrid, k = MENTOR_RAG_TOP_K
    python scripts/eval_retrieval.py --mode vector --k 4
    python scripts/eval_retrieval.py --compare       # vector vs hybrid side by side

Requires GEMINI_API_KEY and Supabase credentials; the passages must have been
ingested with scripts/ingest_sources.py. Extend tests/data/retrieval_golden.json
as you notice weak spots; every entry is a regression test for ranking.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.services.mentor_rag import retrieve_passages  # noqa: E402
from app.services.retrieval_eval import evaluate_retrieval  # noqa: E402

GOLDEN = Path(__file__).resolve().parents[1] / "tests" / "data" / "retrieval_golden.json"


async def run(mode: str, k: int) -> dict:
    golden = json.loads(GOLDEN.read_text())
    results = {}
    for item in golden:
        passages = await retrieve_passages(item["mentor_id"], item["query"], k, mode=mode)
        results[item["query"]] = [p["chunk"] for p in passages]
    return evaluate_retrieval(golden, results, k)


def show(mode: str, report: dict) -> None:
    print(f"{mode:>7}: recall@{report['k']} = {report['recall_at_k']:.2f}   MRR = {report['mrr']:.2f}   (n={report['n']})")
    for miss in report["misses"]:
        print(f"         miss  [{miss['mentor_id']}] {miss['query']}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=settings.MENTOR_RAG_MODE, choices=["vector", "hybrid"])
    ap.add_argument("--k", type=int, default=settings.MENTOR_RAG_TOP_K)
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    modes = ["vector", "hybrid"] if args.compare else [args.mode]
    for mode in modes:
        show(mode, await run(mode, args.k))


if __name__ == "__main__":
    asyncio.run(main())
