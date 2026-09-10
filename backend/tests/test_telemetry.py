"""
Telemetry: percentiles, cost estimation, per-purpose/per-route aggregates,
per-context usage capture and the state reducer, plus include_raw unpacking
in the structured-output path.
"""

import pytest
from langchain_core.messages import AIMessage

from app.core.config import settings
from app.models.ai_schemas import JudgeVerdict
from app.services import ai_service
from app.services import telemetry as tm
from app.services.ai_service import AIServiceError


@pytest.fixture(autouse=True)
def fresh():
    tm.telemetry.reset()
    yield
    tm.telemetry.reset()


# ─── Maths ────────────────────────────────────────────────────────────────────

def test_percentile_nearest_rank():
    assert tm.percentile([], 95) is None
    assert tm.percentile([10], 95) == 10
    assert tm.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5
    assert tm.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert tm.percentile([5, 1, 3], 50) == 3


def test_cost_uses_price_table_per_model(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PRICE_INPUT_PER_M", {"m": 0.05, "default": 0.0})
    monkeypatch.setattr(settings, "LLM_PRICE_OUTPUT_PER_M", {"m": 0.08, "default": 0.0})
    assert tm.estimate_cost_usd("m", 1_000_000, 1_000_000) == pytest.approx(0.13)
    assert tm.estimate_cost_usd("m", 2000, 500) == pytest.approx((2000 * 0.05 + 500 * 0.08) / 1e6)
    assert tm.estimate_cost_usd("unknown-model", 10**6, 10**6) == 0.0          # falls back to default


def test_usage_from_message():
    m = AIMessage(content="x", usage_metadata={"input_tokens": 12, "output_tokens": 3, "total_tokens": 15})
    assert tm.usage_from_message(m) == {"prompt_tokens": 12, "completion_tokens": 3, "reported": True}
    assert tm.usage_from_message(AIMessage(content="x")) == {"prompt_tokens": 0, "completion_tokens": 0, "reported": False}
    assert tm.usage_from_message(None)["reported"] is False


# ─── Aggregates ───────────────────────────────────────────────────────────────

def test_llm_snapshot_aggregates_by_purpose():
    for latency, pt, ct in [(100, 500, 50), (300, 700, 70), (200, 600, 60)]:
        tm.telemetry.record_llm_call(purpose="tutor", model="llama-3.1-8b-instant",
                                     usage={"prompt_tokens": pt, "completion_tokens": ct, "reported": True}, latency_ms=latency)
    tm.telemetry.record_llm_call(purpose="llm_judge", model="llama-3.1-8b-instant",
                                 usage={"prompt_tokens": 0, "completion_tokens": 0, "reported": False}, latency_ms=0, error=True)
    snap = tm.telemetry.snapshot()
    tutor = snap["llm"]["tutor"]
    assert tutor["count"] == 3 and tutor["errors"] == 0
    assert tutor["prompt_tokens"] == 1800 and tutor["completion_tokens"] == 180
    assert tutor["avg_prompt_tokens"] == 600.0
    assert tutor["p50_ms"] == 200 and tutor["p95_ms"] == 300 and tutor["max_ms"] == 300
    assert tutor["usage_reported_ratio"] == 1.0
    assert tutor["cost_usd"] == pytest.approx((1800 * 0.05 + 180 * 0.08) / 1e6, abs=1e-9)
    judge = snap["llm"]["llm_judge"]
    assert judge["count"] == 1 and judge["errors"] == 1 and judge["usage_reported_ratio"] == 0.0
    assert snap["llm_totals"]["calls"] == 4
    assert "resets on restart" in snap["note"]


def test_http_snapshot_counts_errors_as_5xx_only():
    for status in (200, 200, 404, 500):
        tm.telemetry.record_request(route="/api/v1/session/{session_id}", method="GET", status=status, latency_ms=10)
    s = tm.telemetry.snapshot()["http"]["GET /api/v1/session/{session_id}"]
    assert s["count"] == 4 and s["errors"] == 1


# ─── Per-context usage capture ────────────────────────────────────────────────

def test_drain_usage_sums_and_clears():
    tm.begin_usage_capture()
    tm.telemetry.record_llm_call(purpose="tutor", model="llama-3.1-8b-instant",
                                 usage={"prompt_tokens": 100, "completion_tokens": 10, "reported": True}, latency_ms=1)
    tm.telemetry.record_llm_call(purpose="tutor", model="llama-3.1-8b-instant",
                                 usage={"prompt_tokens": 50, "completion_tokens": 5, "reported": True}, latency_ms=1)
    drained = tm.drain_usage()
    assert drained["llm_calls"] == 2 and drained["prompt_tokens"] == 150 and drained["completion_tokens"] == 15
    assert drained["cost_usd"] == pytest.approx((150 * 0.05 + 15 * 0.08) / 1e6, abs=1e-9)
    assert tm.drain_usage()["llm_calls"] == 0                       # cleared


def test_drain_without_capture_is_zero():
    assert tm.drain_usage() == {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}


def test_add_usage_reducer_sums_elementwise():
    a = {"llm_calls": 1, "prompt_tokens": 10, "completion_tokens": 1, "cost_usd": 0.001}
    b = {"llm_calls": 2, "prompt_tokens": 20, "completion_tokens": 2, "cost_usd": 0.002}
    assert tm.add_usage(a, b) == {"llm_calls": 3, "prompt_tokens": 30, "completion_tokens": 3, "cost_usd": 0.003}
    assert tm.add_usage(None, b) == b


# ─── Structured output keeps usage via include_raw ────────────────────────────

class _Runnable:
    def __init__(self, payload):
        self.payload = payload

    async def ainvoke(self, messages):
        return self.payload


async def test_structured_call_records_usage_from_raw_message(monkeypatch):
    raw = AIMessage(content="", usage_metadata={"input_tokens": 400, "output_tokens": 40, "total_tokens": 440})
    parsed = JudgeVerdict(score=0.5, understood=[], gaps=[], reasoning="r")
    monkeypatch.setattr(ai_service, "_structured_llm",
                        lambda schema, temperature: _Runnable({"raw": raw, "parsed": parsed, "parsing_error": None}))
    monkeypatch.setattr(ai_service, "get_topic_context", lambda topic, topic_id=None: {"explanation": "e", "key_takeaway": "k", "mentor_id": "einstein"})

    tm.begin_usage_capture()
    result = await ai_service.evaluate_understanding("t", [])

    assert result is parsed
    assert tm.telemetry.snapshot()["llm"]["llm_judge"]["prompt_tokens"] == 400
    assert tm.drain_usage()["prompt_tokens"] == 400


async def test_parsing_error_in_raw_triggers_retry_then_503_path(monkeypatch):
    raw = AIMessage(content="not json")
    monkeypatch.setattr(ai_service, "_structured_llm",
                        lambda schema, temperature: _Runnable({"raw": raw, "parsed": None, "parsing_error": ValueError("bad")}))
    monkeypatch.setattr(ai_service, "get_topic_context", lambda topic, topic_id=None: {"mentor_id": "einstein"})
    with pytest.raises(AIServiceError):
        await ai_service.evaluate_understanding("t", [])
    judge = tm.telemetry.snapshot()["llm"]["llm_judge"]
    assert judge["count"] == 2 and judge["errors"] == 2                 # both attempts recorded as errors
