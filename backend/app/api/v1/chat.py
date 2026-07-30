from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
import structlog
from datetime import datetime

from app.core.security import get_current_user
from app.core.database import get_supabase
from app.models.schemas import ChatRequest, ChatEvaluateRequest, ChatEvaluateResponse
from app.services import ai_service

router = APIRouter(prefix="/chat", tags=["Chat"])
limiter = Limiter(key_func=get_remote_address)
log = structlog.get_logger()


def update_user_mastery_db(user_id: str, topic_id: str, score: float, history: list, eval_result: dict):
    """Background task to save the evaluated mastery level to Supabase."""
    try:
        supabase_client = get_supabase()
        # Check if record exists
        response = supabase_client.table("user_mastery").select("*").eq("user_id", user_id).eq("topic_id", topic_id).execute()
        
        if response.data:
            supabase_client.table("user_mastery").update({
                "mastery_level": score,
                "last_attempted_at": datetime.utcnow().isoformat() + "Z"
            }).eq("user_id", user_id).eq("topic_id", topic_id).execute()
        else:
            supabase_client.table("user_mastery").insert({
                "user_id": user_id,
                "topic_id": topic_id,
                "mastery_level": score,
                "questions_attempted": 0,
                "questions_correct": 0
            }).execute()
        
        # Also trigger badge updates if score is high
        if score >= 0.9:
            supabase_client.table("user_badges").insert({
                "user_id": user_id,
                "badge_name": "Master"
            }).execute()
        elif score >= 0.7:
            supabase_client.table("user_badges").insert({
                "user_id": user_id,
                "badge_name": "Expert"
            }).execute()
            
        log.info("user_mastery_updated_via_judge", user_id=user_id, topic_id=topic_id, score=score)
        # Save telemetry
        try:
            supabase_client.table("ai_eval_logs").insert({
                "user_id": user_id,
                "topic_id": topic_id,
                "chat_history": history,
                "ai_response": eval_result,
                "mastery_score": score
            }).execute()
        except Exception as e:
            log.error("telemetry_log_failed", error=str(e))
            
        # Save long-term memory
        gaps = eval_result.get("gaps", [])
        if gaps:
            summary = f"Student previously struggled with: {', '.join(gaps)}. AI noted: {eval_result.get('reasoning', '')}"
            try:
                mem_res = supabase_client.table("user_memories").select("id").eq("user_id", user_id).eq("topic_id", topic_id).execute()
                if mem_res.data:
                    supabase_client.table("user_memories").update({
                        "summary": summary,
                        "updated_at": datetime.utcnow().isoformat() + "Z"
                    }).eq("id", mem_res.data[0]["id"]).execute()
                else:
                    supabase_client.table("user_memories").insert({
                        "user_id": user_id,
                        "topic_id": topic_id,
                        "summary": summary
                    }).execute()
            except Exception as e:
                log.error("memory_update_failed", error=str(e))
            
    except Exception as e:
        log.error("user_mastery_update_failed", user_id=user_id, error=str(e))


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

    past_memory = None
    if body.topic_id:
        try:
            supabase_client = get_supabase()
            mem_res = supabase_client.table("user_memories").select("summary").eq("user_id", user["id"]).eq("topic_id", body.topic_id).execute()
            if mem_res.data:
                past_memory = mem_res.data[0]["summary"]
                log.info("injected_past_memory", user_id=user["id"], topic=body.topic)
        except Exception as e:
            log.error("memory_fetch_failed", error=str(e))

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
    
    # 2. Run evaluation
    result = await ai_service.evaluate_understanding(body.topic, history_dicts)
    
    # 3. Schedule database update in background
    background_tasks.add_task(
        update_user_mastery_db,
        user_id=user["id"],
        topic_id=body.topic_id,
        score=result.get("score", 0.5),
        history=history_dicts,
        eval_result=result
    )
    
    return ChatEvaluateResponse(
        success=True,
        score=result.get("score", 0.5),
        understood=result.get("understood", []),
        gaps=result.get("gaps", []),
        reasoning=result.get("reasoning", "Evaluation completed successfully.")
    )
