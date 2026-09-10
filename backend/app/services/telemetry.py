"""
Telemetry: turn every LLM call and HTTP request into numbers.

Two views of the same data:

1. Process aggregates (`snapshot()`): per purpose (tutor, llm_judge, …) call
   counts, prompt/completion tokens, estimated cost, p50/p95 latency; per HTTP
   route request counts, p50/p95 latency, error rate. Served by GET /metrics.
   In-memory and per process: they reset on restart and are not shared across
   instances, which is fine for "what does a session cost" and "what is p95",
   and honest about it in the payload (`since`, `process`).

2. Per-session usage. Graph nodes call `drain_usage()` after their LLM calls
   and store the totals in graph state, so `GET /session/{id}` reports tokens
   and cost for that session even after a restart.

Cost is an estimate from a per-million-token price table in settings. Verify
the prices against the provider's pricing page; the defaults are documented.
"""

import math
import os
import time
from collections import defaultdict, deque
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from app.core.config import settings

log = structlog.get_logger()

MAX_SAMPLES = 5000

# Usages recorded in the current async context since the last drain. Set by
# the session routes per request; nodes drain it into state.
_usage_buffer: ContextVar[list[dict] | None] = ContextVar("llm_usage_buffer", default=None)


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile; None for no data."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def estimate_cost_usd(model: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    """USD estimate from the configured per-million prices (0 if unknown)."""
    price_in = settings.LLM_PRICE_INPUT_PER_M.get(model or "", settings.LLM_PRICE_INPUT_PER_M.get("default", 0.0))
    price_out = settings.LLM_PRICE_OUTPUT_PER_M.get(model or "", settings.LLM_PRICE_OUTPUT_PER_M.get("default", 0.0))
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000


def usage_from_message(message) -> dict:
    """Normalise LangChain usage_metadata into {prompt_tokens, completion_tokens, reported}."""
    meta = getattr(message, "usage_metadata", None) or {}
    if not meta:
        return {"prompt_tokens": 0, "completion_tokens": 0, "reported": False}
    return {
        "prompt_tokens": int(meta.get("input_tokens", 0) or 0),
        "completion_tokens": int(meta.get("output_tokens", 0) or 0),
        "reported": True,
    }


@dataclass
class _Series:
    count: int = 0
    errors: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reported_calls: int = 0
    cost_usd: float = 0.0
    latencies_ms: deque = field(default_factory=lambda: deque(maxlen=MAX_SAMPLES))

    def summary(self) -> dict:
        lat = list(self.latencies_ms)
        return {
            "count": self.count,
            "errors": self.errors,
            "p50_ms": percentile(lat, 50),
            "p95_ms": percentile(lat, 95),
            "max_ms": max(lat) if lat else None,
        }


class Telemetry:
    def __init__(self):
        self.started_at = datetime.now(timezone.utc)
        self.llm: dict[str, _Series] = defaultdict(_Series)
        self.http: dict[str, _Series] = defaultdict(_Series)

    # ── LLM calls ────────────────────────────────────────────────────────────
    def record_llm_call(self, *, purpose: str, model: str | None, usage: dict, latency_ms: float, error: bool = False) -> dict:
        cost = estimate_cost_usd(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        s = self.llm[purpose]
        s.count += 1
        s.errors += int(error)
        s.prompt_tokens += usage.get("prompt_tokens", 0)
        s.completion_tokens += usage.get("completion_tokens", 0)
        s.reported_calls += int(bool(usage.get("reported")))
        s.cost_usd += cost
        s.latencies_ms.append(latency_ms)

        entry = {
            "purpose": purpose,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "reported": bool(usage.get("reported")),
            "cost_usd": cost,
            "latency_ms": round(latency_ms, 1),
        }
        buf = _usage_buffer.get()
        if buf is not None:
            buf.append(entry)
        log.info("llm_call", **entry, error=error)
        return entry

    # ── HTTP ─────────────────────────────────────────────────────────────────
    def record_request(self, *, route: str, method: str, status: int, latency_ms: float) -> None:
        s = self.http[f"{method} {route}"]
        s.count += 1
        s.errors += int(status >= 500)
        s.latencies_ms.append(latency_ms)

    # ── Reporting ────────────────────────────────────────────────────────────
    def snapshot(self) -> dict:
        llm = {}
        for purpose, s in sorted(self.llm.items()):
            llm[purpose] = {
                **s.summary(),
                "prompt_tokens": s.prompt_tokens,
                "completion_tokens": s.completion_tokens,
                "avg_prompt_tokens": round(s.prompt_tokens / s.count, 1) if s.count else None,
                "avg_completion_tokens": round(s.completion_tokens / s.count, 1) if s.count else None,
                "usage_reported_ratio": round(s.reported_calls / s.count, 2) if s.count else None,
                "cost_usd": round(s.cost_usd, 8),
            }
        http = {route: s.summary() for route, s in sorted(self.http.items())}
        total_cost = sum(s.cost_usd for s in self.llm.values())
        total_calls = sum(s.count for s in self.llm.values())
        return {
            "since": self.started_at.isoformat(),
            "process": os.getpid(),
            "llm": llm,
            "llm_totals": {"calls": total_calls, "cost_usd": round(total_cost, 8)},
            "http": http,
            "note": "In-memory, per process; resets on restart. Cost uses the LLM_PRICE_* settings.",
        }

    def reset(self) -> None:
        self.llm.clear()
        self.http.clear()
        self.started_at = datetime.now(timezone.utc)


telemetry = Telemetry()


# ─── Per-context usage buffer ─────────────────────────────────────────────────

def begin_usage_capture() -> None:
    """Start collecting LLM usage in the current async context (one request)."""
    _usage_buffer.set([])


def drain_usage() -> dict:
    """
    Sum and clear the usage recorded since capture began (or since the last
    drain). Returns a dict shaped for the session state's `usage` reducer.
    """
    buf = _usage_buffer.get()
    if not buf:
        return {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
    total = {
        "llm_calls": len(buf),
        "prompt_tokens": sum(e["prompt_tokens"] for e in buf),
        "completion_tokens": sum(e["completion_tokens"] for e in buf),
        "cost_usd": round(sum(e["cost_usd"] for e in buf), 8),
    }
    buf.clear()
    return total


def add_usage(a: dict | None, b: dict | None) -> dict:
    """Reducer for SessionState['usage']: element-wise sum."""
    a = a or {}
    b = b or {}
    keys = {"llm_calls", "prompt_tokens", "completion_tokens", "cost_usd"}
    out = {k: (a.get(k, 0) or 0) + (b.get(k, 0) or 0) for k in keys}
    out["cost_usd"] = round(out["cost_usd"], 8)
    return out


class timer:
    """`with timer() as t: ...; t.ms`"""

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = (time.perf_counter() - self._t0) * 1000.0
        return False
