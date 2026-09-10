import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.security import get_current_user
from app.models.schemas import ChatEvaluateRequest, ChatEvaluateResponse, ChatRequest
from app.services import ai_service
from app.services.ai_service import AIServiceError
from app.services.persistence import fetch_past_memory, persist_evaluation

router = APIRouter(prefix="/chat", tags=["Chat"])
limiter = Limiter(key_func=get_remote_address)
log = structlog.get_logger()


@router.post("")
@limiter.limit("10/minute")
async def chat_with_tutor(
    request: Request,
    body: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """
    AI Tutor Socratic chat with streaming response via Server-Sent Events (SSE).
    """
    log.info(
        "chat_request",
        user_id=user["id"],
        topic=body.topic,
        mastery=body.mastery,
        persona=body.persona_id,
    )

    past_memory = await fetch_past_memory(user["id"], body.topic_id)
    if past_memory:
        log.info("injected_past_memory", user_id=user["id"], topic=body.topic)

    return StreamingResponse(
        ai_service.stream_tutor_response(
            body.message, body.topic, body.mastery, body.history,
            persona_id=body.persona_id, past_memory=past_memory
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/evaluate", response_model=ChatEvaluateResponse)
@limiter.limit("5/minute")
async def evaluate_chat(
    request: Request,
    body: ChatEvaluateRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """
    Perform LLM-as-Judge evaluation on the Socratic tutor session.
    Returns structured feedback (understood concepts, gaps) and saves mastery in DB.
    """
    log.info("chat_evaluation_request", user_id=user["id"], topic=body.topic)

    # 1. Convert schema message history to dict list
    history_dicts = [{"role": msg.role, "content": msg.content} for msg in body.history]

    # 2. Run evaluation. A model/schema failure is an honest 503, not a fake 0.5.
    try:
        verdict = await ai_service.evaluate_understanding(body.topic, history_dicts)
    except AIServiceError as e:
        log.error("llm_judge_unavailable", user_id=user["id"], topic=body.topic, error=str(e))
        raise HTTPException(
            status_code=503,
            detail="Evaluation is temporarily unavailable. Please try again in a moment.",
        ) from e

    eval_result = verdict.model_dump()

    # 3. Schedule database update in background
    background_tasks.add_task(
        persist_evaluation,
        user_id=user["id"],
        topic_id=body.topic_id,
        score=verdict.score,
        history=history_dicts,
        eval_result=eval_result,
    )

    return ChatEvaluateResponse(
        success=True,
        score=verdict.score,
        understood=verdict.understood,
        gaps=verdict.gaps,
        reasoning=verdict.reasoning,
    )
