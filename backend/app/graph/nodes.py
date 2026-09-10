"""
Nodes of the session graph. Each is an async function that receives the whole
SessionState and returns only the keys it changes.

Nodes that need the student pause the graph with `interrupt(payload)`. LangGraph
checkpoints the state, the API returns `payload` to the client, and when the
client resumes with `Command(resume=value)` the node re-runs from its top and
`interrupt()` returns `value`. Nodes containing an interrupt therefore do no
work before the interrupt call.

LLM and database access go through `ai_service` and `persistence`, the same
modules the legacy endpoints use, so tests can fake them in one place.
"""

import structlog
from langgraph.types import interrupt

from app.graph.state import (
    MIN_STUDENT_TURNS,
    PHASE_DONE,
    PHASE_QUIZ,
    PHASE_TUTOR,
    QUIZ_LENGTH,
    SessionState,
    public_question,
)
from app.services import ai_service, persistence
from app.services.mastery_service import (
    mastery_to_theta,
    select_difficulty,
    theta_to_mastery,
    update_theta_eap,
)
from app.services.telemetry import drain_usage, telemetry, timer, usage_from_message

log = structlog.get_logger()


# ─── Setup ────────────────────────────────────────────────────────────────────

async def init(state: SessionState) -> dict:
    """Load episodic memory once and enter the tutoring phase."""
    past_memory = await persistence.fetch_past_memory(state["user_id"], state.get("topic_id"))
    mastery = float(state.get("mastery", 0.0) or 0.0)
    return {
        "phase": PHASE_TUTOR,
        "past_memory": past_memory,
        "mastery": mastery,
        "theta": mastery_to_theta(mastery),
        "theta_sd": 1.0,
        "student_turns": state.get("student_turns", 0),
        "quiz_index": 0,
        "verdict": None,
        "resume": None,
    }


# ─── Tutoring loop ────────────────────────────────────────────────────────────

async def await_student(state: SessionState) -> dict:
    """Pause until the student sends a message or asks for evaluation."""
    turns = state.get("student_turns", 0)
    payload = interrupt({
        "type": "student_turn",
        "student_turns": turns,
        "can_evaluate": turns >= MIN_STUDENT_TURNS,
    })
    return {"resume": payload}


def route_after_student(state: SessionState) -> str:
    resume = state.get("resume") or {}
    if resume.get("action") == "evaluate":
        # Guard duplicated in the API (400); here it keeps the graph honest.
        return "judge" if state.get("student_turns", 0) >= MIN_STUDENT_TURNS else "await_student"
    return "tutor_reply" if str(resume.get("message", "")).strip() else "await_student"


async def tutor_reply(state: SessionState) -> dict:
    """One Socratic turn. The LLM call streams token-by-token to the API via stream_mode='messages'."""
    message = str((state.get("resume") or {}).get("message", "")).strip()
    lc_messages, persona_id = await ai_service.build_tutor_messages(
        message=message,
        topic=state["topic"],
        mastery=state.get("mastery", 0.0),
        history=state.get("messages", []),
        persona_id=state.get("persona_id"),
        past_memory=state.get("past_memory"),
    )
    with timer() as t:
        reply = await ai_service._make_llm(temperature=0.7).ainvoke(lc_messages)
    telemetry.record_llm_call(purpose="tutor", model=ai_service.GROQ_MODEL, usage=usage_from_message(reply), latency_ms=t.ms)
    content = reply.content if isinstance(reply.content, str) else str(reply.content)
    return {
        "messages": [
            {"role": "user", "content": message},
            {"role": "assistant", "content": content},
        ],
        "student_turns": state.get("student_turns", 0) + 1,
        "persona_id": persona_id,
        "resume": None,
        "usage": drain_usage(),
    }


# ─── Judge ────────────────────────────────────────────────────────────────────

async def judge(state: SessionState) -> dict:
    """LLM-as-Judge over the full transcript; persists mastery + memory; moves to the quiz."""
    verdict = await ai_service.evaluate_understanding(
        state["topic"], state.get("messages", []), persona_id=state.get("persona_id")
    )
    result = verdict.model_dump()
    await persistence.persist_evaluation(
        state["user_id"], state["topic_id"], verdict.score, state.get("messages", []), result
    )
    log.info("session_judged", topic=state["topic"], score=verdict.score)
    return {
        "verdict": result,
        "mastery": verdict.score,
        "theta": mastery_to_theta(verdict.score),
        "phase": PHASE_QUIZ,
        "quiz_index": 0,
        "resume": None,
        "usage": drain_usage(),
    }


# ─── Adaptive quiz loop ───────────────────────────────────────────────────────

async def quiz_generate(state: SessionState) -> dict:
    """Generate the next question at the difficulty band nearest θ. The answer key stays in state."""
    label, b = select_difficulty(state["theta"])
    gaps = (state.get("verdict") or {}).get("gaps") or []
    generated = await ai_service.generate_question(state["topic"], label, gaps, persona_id=state.get("persona_id"))
    question = {
        "index": state.get("quiz_index", 0),
        "question": generated.question,
        "options": generated.options,
        "correct_answer": generated.correct_answer,
        "difficulty": label,
        "difficulty_param": b,
    }
    return {"questions": [question], "resume": None, "usage": drain_usage()}


async def await_answer(state: SessionState) -> dict:
    """Pause with the public view of the current question until the student answers."""
    current = state["questions"][-1]
    payload = interrupt({
        "type": "question",
        "question": public_question(current),
        "index": current["index"],
        "total": QUIZ_LENGTH,
        "theta": state["theta"],
        "mastery": state["mastery"],
    })
    return {"resume": payload}


async def grade_answer(state: SessionState) -> dict:
    """Grade against the server-held key, update θ with the EAP step, persist counters."""
    current = state["questions"][-1]
    answer = str((state.get("resume") or {}).get("answer", "")).strip()
    verdict = await ai_service.evaluate_answer(state["topic"], current["question"], answer, current["correct_answer"])
    new_theta, new_sd = update_theta_eap(state["theta"], verdict.is_correct, current["difficulty_param"])
    await persistence.persist_quiz_answer(state["user_id"], state["topic_id"], verdict.is_correct)
    graded = {
        "index": current["index"],
        "answer": answer,
        "is_correct": verdict.is_correct,
        "score": verdict.score,
        "feedback": verdict.feedback,
        "correction": verdict.correction,
        "correct_answer": current["correct_answer"],  # revealed only after grading
    }
    return {
        "answers": [graded],
        "theta": new_theta,
        "theta_sd": new_sd,
        "mastery": theta_to_mastery(new_theta),
        "quiz_index": current["index"] + 1,
        "resume": None,
        "usage": drain_usage(),
    }


def route_after_grade(state: SessionState) -> str:
    return "quiz_generate" if state.get("quiz_index", 0) < QUIZ_LENGTH else "finish"


async def finish(state: SessionState) -> dict:
    log.info("session_complete", topic=state["topic"], mastery=state.get("mastery"))
    return {"phase": PHASE_DONE, "resume": None}
