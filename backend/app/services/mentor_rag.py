"""
Mentor RAG: ground each persona in the mentor's own public-domain writings.

The curriculum row (`get_topic_context`) stays the deterministic anchor for
*what* to teach. This module adds *voice and examples*: for every tutor turn we
embed the student's message, retrieve the most relevant passages from
`mentor_passages` for the active mentor, and put them in the system prompt.

Retrieval modes (MENTOR_RAG_MODE):
  hybrid  — vector similarity + full-text keyword rank, fused with Reciprocal
            Rank Fusion in SQL (match_mentor_passages_hybrid). Default.
  vector  — cosine similarity only (match_mentor_passages).
  off     — skip retrieval; prompt unchanged.

Everything fails open: no key, no rows, embedding or RPC error → no passages,
and the tutor answers exactly as it did before this module existed.

Chunking lives here too so the ingestion script and the tests share it.
"""

import asyncio
import re
from typing import Any

import structlog

from app.core.config import settings
from app.core.database import get_supabase

log = structlog.get_logger()

# Gutenberg plain-text files wrap the work in licence boilerplate delimited by
# these markers (the exact wording varies slightly between files).
_GUTENBERG_START = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.IGNORECASE | re.DOTALL)
_GUTENBERG_END = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK.*", re.IGNORECASE | re.DOTALL)


# ─── Text preparation ─────────────────────────────────────────────────────────

def strip_gutenberg_boilerplate(text: str) -> str:
    """Keep only the body between the START and END markers (or the whole text if absent)."""
    start = _GUTENBERG_START.search(text)
    if start:
        text = text[start.end():]
    end = _GUTENBERG_END.search(text)
    if end:
        text = text[: end.start()]
    return text.strip()


def chunk_text(text: str, size_words: int = 300, overlap_words: int = 50) -> list[str]:
    """
    Split text into overlapping word windows.

    ~300 words ≈ 400 tokens: big enough to carry an argument, small enough
    that 3–4 chunks fit comfortably in a prompt. The overlap means a sentence
    straddling a boundary is still findable from either side.
    """
    if size_words <= 0 or overlap_words < 0 or overlap_words >= size_words:
        raise ValueError("need size_words > overlap_words >= 0")
    words = re.sub(r"\s+", " ", text).strip().split(" ")
    words = [w for w in words if w]
    if not words:
        return []
    step = size_words - overlap_words
    chunks = []
    for start in range(0, len(words), step):
        window = words[start : start + size_words]
        chunks.append(" ".join(window))
        if start + size_words >= len(words):
            break
    return chunks


# ─── Embeddings ───────────────────────────────────────────────────────────────

class GeminiEmbedder:
    """Embeds text with the Gemini embedding model; documents and queries use different task types."""

    def __init__(self, api_key: str, model: str, dimensions: int):
        self._api_key, self.model, self.dimensions = api_key, model, dimensions

    async def embed(self, texts: list[str], *, task_type: str) -> list[list[float]]:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=self._api_key)
        result = await asyncio.to_thread(
            client.models.embed_content,
            model=self.model,
            contents=texts,
            config=genai_types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dimensions),
        )
        return [list(e.values) for e in result.embeddings]


def default_embedder() -> GeminiEmbedder | None:
    if not settings.GEMINI_API_KEY:
        return None
    return GeminiEmbedder(settings.GEMINI_API_KEY, settings.MENTOR_EMBED_MODEL, settings.MENTOR_EMBED_DIMENSIONS)


# ─── Retrieval ────────────────────────────────────────────────────────────────

def _rpc(name: str, params: dict) -> list[dict]:
    """Synchronous supabase-py call, run in a worker thread by the caller."""
    res = get_supabase().rpc(name, params).execute()
    return list(res.data or [])


async def retrieve_passages(
    mentor_id: str | None,
    query: str,
    k: int | None = None,
    *,
    embedder=None,
    mode: str | None = None,
) -> list[dict[str, Any]]:
    """
    Top-k passages for `mentor_id` relevant to `query`.
    Returns [] whenever retrieval is off, unavailable, or fails.
    """
    mode = (mode or settings.MENTOR_RAG_MODE or "off").lower()
    k = k if k is not None else settings.MENTOR_RAG_TOP_K
    if mode == "off" or k <= 0 or not mentor_id or not query.strip():
        return []
    embedder = embedder or default_embedder()
    if embedder is None:
        return []
    try:
        [qvec] = await embedder.embed([query], task_type="RETRIEVAL_QUERY")
        if mode == "hybrid":
            rows = await asyncio.to_thread(_rpc, "match_mentor_passages_hybrid", {
                "p_mentor_id": mentor_id, "p_query_text": query, "p_query_embedding": qvec, "p_match_count": k,
            })
        else:
            rows = await asyncio.to_thread(_rpc, "match_mentor_passages", {
                "p_mentor_id": mentor_id, "p_query_embedding": qvec, "p_match_count": k,
            })
    except Exception as e:
        log.warning("mentor_rag_failed", mentor=mentor_id, mode=mode, error=str(e)[:200])
        return []

    passages = [
        {
            "source": r.get("source", ""),
            "chunk_index": r.get("chunk_index"),
            "chunk": r.get("chunk", ""),
            "score": r.get("score", r.get("similarity")),
        }
        for r in rows
        if r.get("chunk")
    ]
    log.info("mentor_rag_retrieved", mentor=mentor_id, mode=mode, k=k, hits=len(passages))
    return passages


def format_passages(passages: list[dict[str, Any]]) -> str:
    """Numbered passages with their source, for the system prompt."""
    lines = []
    for i, p in enumerate(passages, 1):
        where = p["source"] + (f", passage {p['chunk_index']}" if p.get("chunk_index") is not None else "")
        lines.append(f"[{i}] ({where}) {p['chunk'].strip()}")
    return "\n\n".join(lines)
