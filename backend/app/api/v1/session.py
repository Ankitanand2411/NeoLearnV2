"""
/session/* — the server-side learning session, backed by the LangGraph state
machine in app.graph. Replaces the client-side flow of /chat → /chat/evaluate →
/quiz/generate → /quiz/evaluate (those routes remain for one release).

Thread ownership: the LangGraph thread id is f"{user_id}:{session_id}", built
from the authenticated user on every request, so a session id from another
account resolves to a thread that does not exist (404), never to their data.
"""

import json
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.security import get_current_user
from app.graph.state import MIN_STUDENT_TURNS, PHASE_DONE, PHASE_QUIZ, PHASE_TUTOR, QUIZ_LENGTH
from app.services.ai_service import AIServiceError
from app.services.telemetry import begin_usage_capture

router = APIRouter(prefix="/session", tags=["Session"])
limiter = Limiter(key_func=get_remote_address)
log = structlog.get_logger()

_UNAVAILABLE = "The tutor is temporarily unavailable. Please try again in a moment."


# ─── Schemas ──────────────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    topic_id: str
    topic: str = Field(..., min_length=1)
    persona_id: str | None = None
    mastery: float = Field(0.0, ge=0.0, le=1.0)


class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=2000)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_graph(request: Request):
    graph = getattr(request.app.state, "session_graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="Session service is not initialised")
    return graph


def _config(user_id: str, session_id: str) -> dict:
    return {"configurable": {"thread_id": f"{user_id}:{session_id}"}}


def _interrupt_payload(snapshot) -> dict | None:
    for task in snapshot.tasks:
        for intr in task.interrupts:
            return intr.value
    return None


def _pending_step(snapshot) -> str | None:
    """
    Name of a node that is due to run but hasn't completed, or None.

    This is the state after a node raised (e.g. the LLM was down during
    `judge`): the checkpoint recorded that the previous step finished, so the
    graph is parked *before* the failed node rather than at an interrupt.
    Recovery is "continue from the checkpoint" (ainvoke(None)), not a new
    resume value.
    """
    if _interrupt_payload(snapshot) is not None:
        return None
    return snapshot.next[0] if snapshot.next else None


def _view(session_id: str, snapshot) -> dict[str, Any]:
    """Client-safe projection of the checkpointed state. Never includes an unanswered answer key."""
    v = snapshot.values
    intr = _interrupt_payload(snapshot) or {}
    phase = v.get("phase", PHASE_TUTOR)
    turns = v.get("student_turns", 0)
    return {
        "session_id": session_id,
        "phase": phase,
        "pending_step": _pending_step(snapshot),
        "completed": phase == PHASE_DONE,
        "mastery": v.get("mastery", 0.0),
        "theta": v.get("theta", 0.0),
        "theta_sd": v.get("theta_sd"),
        "student_turns": turns,
        "can_evaluate": phase == PHASE_TUTOR and turns >= MIN_STUDENT_TURNS,
        "messages": v.get("messages", []),
        "verdict": v.get("verdict"),
        "question": intr.get("question") if intr.get("type") == "question" else None,
        "quiz": {
            "index": v.get("quiz_index", 0),
            "total": QUIZ_LENGTH,
            "answers": v.get("answers", []),
        },
        "usage": v.get("usage") or {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0},
    }


async def _load(graph, user_id: str, session_id: str):
    snapshot = await graph.aget_state(_config(user_id, session_id))
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="Session not found")
    return snapshot


async def _resume(graph, config: dict, snapshot, value: dict):
    """
    Advance the graph. If it is parked at an interrupt, feed `value` in; if it
    is parked before a step that previously failed, just continue. Either way a
    model outage becomes a 503 and the checkpoint stays where it was, so the
    client can retry the same call.
    """
    payload = Command(resume=value) if _interrupt_payload(snapshot) is not None else None
    begin_usage_capture()
    try:
        await graph.ainvoke(payload, config)
    except AIServiceError as e:
        log.error("session_llm_unavailable", error=str(e))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from e


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/start")
@limiter.limit("10/minute")
async def start_session(request: Request, body: StartSessionRequest, user: dict = Depends(get_current_user)):
    graph = get_graph(request)
    session_id = uuid.uuid4().hex
    config = _config(user["id"], session_id)
    begin_usage_capture()
    await graph.ainvoke(
        {
            "user_id": user["id"],
            "topic_id": body.topic_id,
            "topic": body.topic,
            "persona_id": body.persona_id,
            "mastery": body.mastery,
            "messages": [],
            "questions": [],
            "answers": [],
        },
        config,
    )
    log.info("session_started", user_id=user["id"], topic=body.topic, session_id=session_id)
    return _view(session_id, await graph.aget_state(config))


@router.get("/{session_id}")
async def get_session(request: Request, session_id: str, user: dict = Depends(get_current_user)):
    graph = get_graph(request)
    return _view(session_id, await _load(graph, user["id"], session_id))


@router.post("/{session_id}/message")
@limiter.limit("30/minute")
async def send_message(request: Request, session_id: str, body: MessageRequest, user: dict = Depends(get_current_user)):
    """
    One tutor turn, streamed as SSE:
        data: {"token": "..."}      repeated, from the LLM call inside the graph
        data: {"done": true, "student_turns": n, "can_evaluate": bool}
        data: [DONE]
    """
    graph = get_graph(request)
    snapshot = await _load(graph, user["id"], session_id)
    if snapshot.values.get("phase") != PHASE_TUTOR:
        raise HTTPException(status_code=409, detail="This session is no longer in the tutoring phase")
    if _pending_step(snapshot):
        raise HTTPException(
            status_code=409,
            detail="An evaluation is pending for this session; retry it (or call /continue) before chatting further",
        )
    config = _config(user["id"], session_id)

    async def event_stream():
        begin_usage_capture()
        try:
            async for chunk, meta in graph.astream(
                Command(resume={"message": body.message}), config, stream_mode="messages"
            ):
                if meta.get("langgraph_node") != "tutor_reply":
                    continue
                token = chunk.content if isinstance(chunk.content, str) else ""
                if token:
                    yield f"data: {json.dumps({'token': token})}\n\n"
            after = await graph.aget_state(config)
            turns = after.values.get("student_turns", 0)
            yield f"data: {json.dumps({'done': True, 'student_turns': turns, 'can_evaluate': turns >= MIN_STUDENT_TURNS})}\n\n"
        except Exception as e:  # streaming has already started; report inline
            log.error("session_stream_failed", error=str(e))
            yield f"data: {json.dumps({'error': _UNAVAILABLE})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{session_id}/evaluate")
@limiter.limit("5/minute")
async def evaluate_session(request: Request, session_id: str, user: dict = Depends(get_current_user)):
    """Run the judge over the transcript and serve the first quiz question."""
    graph = get_graph(request)
    snapshot = await _load(graph, user["id"], session_id)
    v = snapshot.values
    if v.get("phase") != PHASE_TUTOR:
        raise HTTPException(status_code=409, detail="This session has already been evaluated")
    if v.get("student_turns", 0) < MIN_STUDENT_TURNS:
        raise HTTPException(
            status_code=400,
            detail=f"At least {MIN_STUDENT_TURNS} student messages are needed before evaluation",
        )
    config = _config(user["id"], session_id)
    await _resume(graph, config, snapshot, {"action": "evaluate"})
    return _view(session_id, await graph.aget_state(config))


@router.post("/{session_id}/continue")
@limiter.limit("30/minute")
async def continue_session(request: Request, session_id: str, user: dict = Depends(get_current_user)):
    """Re-run a step that failed mid-way (e.g. question generation while the model was down)."""
    graph = get_graph(request)
    snapshot = await _load(graph, user["id"], session_id)
    if not _pending_step(snapshot):
        return _view(session_id, snapshot)   # nothing to do; idempotent
    config = _config(user["id"], session_id)
    await _resume(graph, config, snapshot, {})
    return _view(session_id, await graph.aget_state(config))


@router.post("/{session_id}/answer")
@limiter.limit("30/minute")
async def answer_question(request: Request, session_id: str, body: AnswerRequest, user: dict = Depends(get_current_user)):
    """Grade the current question against the server-held key; return the result and the next question (or completion)."""
    graph = get_graph(request)
    snapshot = await _load(graph, user["id"], session_id)
    if snapshot.values.get("phase") != PHASE_QUIZ:
        raise HTTPException(status_code=409, detail="This session is not in the quiz phase")
    config = _config(user["id"], session_id)
    await _resume(graph, config, snapshot, {"answer": body.answer})
    view = _view(session_id, await graph.aget_state(config))
    view["evaluation"] = view["quiz"]["answers"][-1] if view["quiz"]["answers"] else None
    return view
