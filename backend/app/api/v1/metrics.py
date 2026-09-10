"""
GET /metrics — process-level numbers: LLM calls by purpose (tokens, cost,
p50/p95 latency) and HTTP routes (count, p50/p95, errors). JWT-protected.

The payload says so itself: in-memory, per process, resets on restart. For a
single-instance deployment that is exactly the number you want for a README;
for a fleet you would ship the same records to a metrics backend instead.
"""

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.services.telemetry import telemetry

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("")
async def get_metrics(user: dict = Depends(get_current_user)):
    return telemetry.snapshot()
