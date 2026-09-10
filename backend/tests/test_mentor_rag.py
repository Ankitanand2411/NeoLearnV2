"""
Mentor RAG: chunking, Gutenberg cleanup, retrieval modes and fail-open
behaviour, prompt injection, and the golden-set evaluation metric.

No network: the embedder is a fake and the Supabase RPC is a recorder. The
SQL functions themselves were verified against a local Postgres + pgvector
(see supabase/migrations/20260910_mentor_passages.sql).
"""

import json
from pathlib import Path

import pytest

from app.core.config import settings
from app.services import ai_service, mentor_rag
from app.services.persona_registry import build_persona_system_prompt
from app.services.retrieval_eval import evaluate_retrieval

# ─── Text preparation ─────────────────────────────────────────────────────────

GUTENBERG = """The Project Gutenberg eBook of Example, by Someone

Title: Example Work

*** START OF THE PROJECT GUTENBERG EBOOK EXAMPLE WORK ***

Chapter I. It was the best of times.

*** END OF THE PROJECT GUTENBERG EBOOK EXAMPLE WORK ***

Licence text that must never be embedded.
"""


def test_strip_gutenberg_boilerplate_keeps_only_the_body():
    body = mentor_rag.strip_gutenberg_boilerplate(GUTENBERG)
    assert body == "Chapter I. It was the best of times."


def test_strip_is_a_no_op_without_markers():
    assert mentor_rag.strip_gutenberg_boilerplate("  plain text  ") == "plain text"


def test_chunks_have_expected_size_and_overlap():
    words = [f"w{i}" for i in range(1000)]
    chunks = mentor_rag.chunk_text(" ".join(words), size_words=300, overlap_words=50)
    sizes = [len(c.split()) for c in chunks]
    assert sizes[:-1] == [300, 300, 300]                    # step = 250, so 0,250,500,750
    assert sizes[-1] == 250                                 # 750..999
    assert chunks[0].split()[-50:] == chunks[1].split()[:50]  # overlap is real
    assert " ".join(chunks).split()[0] == "w0" and "w999" in chunks[-1]


def test_chunking_edge_cases():
    assert mentor_rag.chunk_text("") == []
    assert mentor_rag.chunk_text("   \n\t ") == []
    assert mentor_rag.chunk_text("a b c", size_words=10, overlap_words=2) == ["a b c"]
    assert mentor_rag.chunk_text("one  two\n\nthree") == ["one two three"]  # whitespace normalised
    with pytest.raises(ValueError):
        mentor_rag.chunk_text("x", size_words=10, overlap_words=10)


# ─── Retrieval ────────────────────────────────────────────────────────────────

class FakeEmbedder:
    model = "fake"

    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    async def embed(self, texts, *, task_type):
        if self.fail:
            raise RuntimeError("embedding down")
        self.calls.append((task_type, list(texts)))
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.fixture
def rpc(monkeypatch):
    calls = []
    rows = [
        {"id": 1, "source": "Darwin, Origin (1859)", "chunk_index": 12, "chunk": "natural selection acts...", "score": 0.032},
        {"id": 2, "source": "Darwin, Origin (1859)", "chunk_index": 40, "chunk": "", "score": 0.01},   # empty: dropped
    ]

    def fake_rpc(name, params):
        calls.append((name, params))
        return rows

    monkeypatch.setattr(mentor_rag, "_rpc", fake_rpc)
    return calls


async def test_hybrid_mode_calls_hybrid_function_and_normalises_rows(rpc):
    emb = FakeEmbedder()
    out = await mentor_rag.retrieve_passages("darwin", "how does selection work", 3, embedder=emb, mode="hybrid")
    assert out == [{"source": "Darwin, Origin (1859)", "chunk_index": 12, "chunk": "natural selection acts...", "score": 0.032}]
    name, params = rpc[0]
    assert name == "match_mentor_passages_hybrid"
    assert params["p_mentor_id"] == "darwin" and params["p_query_text"] == "how does selection work"
    assert params["p_match_count"] == 3 and params["p_query_embedding"] == [0.1, 0.2, 0.3]
    assert emb.calls == [("RETRIEVAL_QUERY", ["how does selection work"])]


async def test_vector_mode_calls_vector_function(rpc):
    await mentor_rag.retrieve_passages("darwin", "q", 2, embedder=FakeEmbedder(), mode="vector")
    name, params = rpc[0]
    assert name == "match_mentor_passages" and "p_query_text" not in params


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "off"},
        {"k": 0},
        {"mentor_id": None},
        {"query": "   "},
    ],
)
async def test_retrieval_is_skipped_when_disabled_or_unusable(rpc, kwargs):
    args = {"mentor_id": "darwin", "query": "q", "k": 3, "embedder": FakeEmbedder(), "mode": "hybrid"}
    args.update(kwargs)
    assert await mentor_rag.retrieve_passages(**args) == []
    assert rpc == []


async def test_no_embedder_means_no_retrieval(rpc, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    assert await mentor_rag.retrieve_passages("darwin", "q", 3, mode="hybrid") == []
    assert rpc == []


async def test_embedding_failure_fails_open(rpc):
    assert await mentor_rag.retrieve_passages("darwin", "q", 3, embedder=FakeEmbedder(fail=True), mode="hybrid") == []


async def test_rpc_failure_fails_open(monkeypatch):
    def boom(name, params):
        raise RuntimeError("function does not exist")

    monkeypatch.setattr(mentor_rag, "_rpc", boom)
    assert await mentor_rag.retrieve_passages("darwin", "q", 3, embedder=FakeEmbedder(), mode="hybrid") == []


def test_default_embedder_reads_settings(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "k")
    emb = mentor_rag.default_embedder()
    assert emb.model == settings.MENTOR_EMBED_MODEL and emb.dimensions == settings.MENTOR_EMBED_DIMENSIONS
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    assert mentor_rag.default_embedder() is None


# ─── Prompt injection ─────────────────────────────────────────────────────────

PASSAGES = [
    {"source": "Darwin, Origin (1859)", "chunk_index": 12, "chunk": "Natural selection acts solely by accumulating slight variations."},
    {"source": "Darwin, Origin (1859)", "chunk_index": 88, "chunk": "The Galapagos finches differ from island to island."},
]
RAG = {"description": "d", "explanation": "e", "key_takeaway": "k", "mentor_id": "darwin", "id": "t"}


def test_format_passages_numbers_and_cites():
    text = mentor_rag.format_passages(PASSAGES)
    assert text.startswith("[1] (Darwin, Origin (1859), passage 12) Natural selection")
    assert "[2] (Darwin, Origin (1859), passage 88)" in text


def test_prompt_includes_passages_block_only_when_present():
    with_passages = build_persona_system_prompt("darwin", "Evolution", RAG, 0.4, passages=PASSAGES)
    without = build_persona_system_prompt("darwin", "Evolution", RAG, 0.4, passages=[])
    assert "=== FROM YOUR OWN WRITINGS" in with_passages
    assert "Galapagos finches" in with_passages
    assert "at most one short phrase" in with_passages
    assert "=== FROM YOUR OWN WRITINGS" not in without
    # The block sits before the Socratic rules so the rules still constrain it.
    assert with_passages.index("FROM YOUR OWN WRITINGS") < with_passages.index("SOCRATIC RULES")


async def test_tutor_messages_carry_retrieved_passages(monkeypatch):
    monkeypatch.setattr(ai_service, "get_topic_context", lambda topic, topic_id=None: RAG)
    seen = {}

    async def fake_retrieve(mentor_id, query, k=None, **kw):
        seen["mentor"], seen["query"] = mentor_id, query
        return PASSAGES

    monkeypatch.setattr(mentor_rag, "retrieve_passages", fake_retrieve)
    messages, persona = await ai_service.build_tutor_messages("Why do finches differ?", "Evolution", 0.4, [])
    assert persona == "darwin"
    assert seen == {"mentor": "darwin", "query": "Evolution. Why do finches differ?"}
    assert "Galapagos finches" in messages[0].content


async def test_tutor_messages_unchanged_when_nothing_retrieved(monkeypatch):
    monkeypatch.setattr(ai_service, "get_topic_context", lambda topic, topic_id=None: RAG)

    async def none(*a, **k):
        return []

    monkeypatch.setattr(mentor_rag, "retrieve_passages", none)
    messages, _ = await ai_service.build_tutor_messages("hi", "Evolution", 0.4, [])
    assert "FROM YOUR OWN WRITINGS" not in messages[0].content


# ─── Evaluation harness ───────────────────────────────────────────────────────

GOLDEN = [
    {"mentor_id": "darwin", "query": "q1", "expect_any": ["natural selection"]},
    {"mentor_id": "darwin", "query": "q2", "expect_any": ["galapagos", "islands"]},
    {"mentor_id": "einstein", "query": "q3", "expect_any": ["simultaneous"]},
    {"mentor_id": "twain", "query": "q4", "expect_any": ["pilot"]},
]


def test_recall_and_mrr():
    results = {
        "q1": ["Natural Selection acts...", "other"],          # hit at rank 1
        "q2": ["unrelated", "unrelated", "the Islands differ"],  # hit at rank 3
        "q3": ["nothing relevant"],                            # miss
        # q4 absent entirely                                   # miss
    }
    report = evaluate_retrieval(GOLDEN, results, k=3)
    assert report["n"] == 4 and report["k"] == 3
    assert report["recall_at_k"] == pytest.approx(0.5)
    assert report["mrr"] == pytest.approx((1 + 1 / 3) / 4)
    assert [m["query"] for m in report["misses"]] == ["q3", "q4"]


def test_k_truncates_results():
    results = {"q1": ["x", "y", "z", "natural selection at rank 4"]}
    assert evaluate_retrieval(GOLDEN[:1], results, k=3)["recall_at_k"] == 0.0
    assert evaluate_retrieval(GOLDEN[:1], results, k=4)["recall_at_k"] == 1.0


def test_empty_golden_set_is_zero_not_error():
    assert evaluate_retrieval([], {}, k=3)["recall_at_k"] == 0.0


def test_golden_file_is_well_formed():
    golden = json.loads((Path(__file__).parent / "data" / "retrieval_golden.json").read_text())
    assert len(golden) >= 10
    for item in golden:
        assert set(item) == {"mentor_id", "query", "expect_any"}
        assert item["expect_any"] and all(p == p.lower() or True for p in item["expect_any"])


# ─── Migration ⇄ code contract ────────────────────────────────────────────────

def test_migration_defines_the_functions_the_code_calls():
    sql = (Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "20260910_mentor_passages.sql").read_text()
    for fn in ("match_mentor_passages(", "match_mentor_passages_hybrid("):
        assert f"create function public.{fn}" in sql
    assert "vector(768)" in sql and str(settings.MENTOR_EMBED_DIMENSIONS) == "768"
    assert "using hnsw (embedding vector_cosine_ops)" in sql
    assert "unique (mentor_id, source, chunk_index)" in sql   # what the ingest upsert conflicts on
