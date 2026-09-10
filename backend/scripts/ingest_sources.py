"""
Ingest public-domain writings of the mentors into `mentor_passages`.

    python scripts/ingest_sources.py --mentor darwin --dry-run     # fetch, chunk, count; no writes
    python scripts/ingest_sources.py --mentor darwin --yes         # embed + upsert
    python scripts/ingest_sources.py --all --yes

Requires GEMINI_API_KEY (embeddings) and the Supabase service key (writes).
Run the migration supabase/migrations/20260910_mentor_passages.sql first.

Sources are Project Gutenberg plain-text editions of works that are in the
public domain. Mentors without clearly public-domain primary texts (Feynman,
Turing's later papers, Curie, Gandhi, Ramanujan) are deliberately absent: do
not ingest copyrighted material. Verify each Gutenberg id against the printed
title before the first real run; ids are stable but were entered by hand.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.database import get_supabase  # noqa: E402
from app.services.mentor_rag import (  # noqa: E402
    GeminiEmbedder,
    chunk_text,
    strip_gutenberg_boilerplate,
)

SOURCES: dict[str, list[dict]] = {
    "darwin": [
        {"gutenberg_id": 1228, "citation": "Darwin, On the Origin of Species (1859)"},
    ],
    "twain": [
        {"gutenberg_id": 245, "citation": "Twain, Life on the Mississippi (1883)"},
    ],
    "nightingale": [
        {"gutenberg_id": 12439, "citation": "Nightingale, Notes on Nursing (1859)"},
    ],
    "einstein": [
        {"gutenberg_id": 5001, "citation": "Einstein, Relativity: The Special and General Theory (1916, tr. Lawson 1920)"},
    ],
    "socrates": [
        {"gutenberg_id": 1656, "citation": "Plato, Apology (tr. Jowett)"},
    ],
}

EMBED_BATCH = 50
UPSERT_BATCH = 100


def gutenberg_url(gid: int) -> str:
    return f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt"


def detect_title(raw: str) -> str:
    for line in raw.splitlines()[:80]:
        if line.lower().startswith("title:"):
            return line.split(":", 1)[1].strip()
    return "(title line not found)"


async def fetch_text(gid: int) -> str:
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        r = await client.get(gutenberg_url(gid))
        r.raise_for_status()
        return r.text


async def ingest(mentor_id: str, source: dict, *, dry_run: bool, yes: bool, replace: bool) -> None:
    raw = await fetch_text(source["gutenberg_id"])
    title = detect_title(raw)
    body = strip_gutenberg_boilerplate(raw)
    chunks = chunk_text(body)
    print(f"[{mentor_id}] #{source['gutenberg_id']} title={title!r} words={len(body.split()):,} chunks={len(chunks)}")

    if dry_run:
        return
    if not yes:
        answer = input(f"  Embed and upsert {len(chunks)} chunks as {source['citation']!r}? [y/N] ").strip().lower()
        if answer != "y":
            print("  skipped")
            return
    if not settings.GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY is required to embed")

    embedder = GeminiEmbedder(settings.GEMINI_API_KEY, settings.MENTOR_EMBED_MODEL, settings.MENTOR_EMBED_DIMENSIONS)
    db = get_supabase()
    if replace:
        db.table("mentor_passages").delete().eq("mentor_id", mentor_id).eq("source", source["citation"]).execute()

    rows: list[dict] = []
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start : start + EMBED_BATCH]
        vectors = await embedder.embed(batch, task_type="RETRIEVAL_DOCUMENT")
        for offset, (chunk, vec) in enumerate(zip(batch, vectors, strict=True)):
            rows.append({
                "mentor_id": mentor_id,
                "source": source["citation"],
                "chunk_index": start + offset,
                "chunk": chunk,
                "embedding": vec,
            })
        print(f"  embedded {min(start + EMBED_BATCH, len(chunks))}/{len(chunks)}", end="\r", flush=True)
    print()

    for start in range(0, len(rows), UPSERT_BATCH):
        db.table("mentor_passages").upsert(
            rows[start : start + UPSERT_BATCH], on_conflict="mentor_id,source,chunk_index"
        ).execute()
    print(f"  upserted {len(rows)} rows")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mentor", action="append", help="mentor id (repeatable)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="fetch and chunk only")
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    ap.add_argument("--replace", action="store_true", help="delete existing rows for the source first")
    args = ap.parse_args()

    mentors = list(SOURCES) if args.all else (args.mentor or [])
    if not mentors:
        ap.error("pass --mentor <id> (repeatable) or --all")
    unknown = [m for m in mentors if m not in SOURCES]
    if unknown:
        ap.error(f"no public-domain sources configured for: {', '.join(unknown)}")

    for mentor_id in mentors:
        for source in SOURCES[mentor_id]:
            await ingest(mentor_id, source, dry_run=args.dry_run, yes=args.yes, replace=args.replace)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    asyncio.run(main())
