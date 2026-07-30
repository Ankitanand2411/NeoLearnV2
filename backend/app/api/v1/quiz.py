from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import structlog

from app.core.security import get_current_user
from app.core.database import get_supabase
from app.models.schemas import (
    GenerateQuestionRequest, GenerateQuestionResponse, QuizQuestion,
    EvaluateAnswerRequest, EvaluateAnswerResponse, EvaluationResult,
)
from app.services import ai_service
from app.services.mastery_service import (
    select_difficulty, update_theta, theta_to_mastery, mastery_to_theta, DIFFICULTY_MAP
)

router = APIRouter(prefix="/quiz", tags=["Quiz"])
limiter = Limiter(key_func=get_remote_address)
log = structlog.get_logger()


@router.post("/generate", response_model=GenerateQuestionResponse)
@limiter.limit("20/minute")
async def generate_question(
    request: Request,
    body: GenerateQuestionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Generate an adaptive question using IRT-based difficulty selection.
    
    The difficulty is selected to maximize Fisher information at the
    student's current ability estimate (theta).
    """
    theta = mastery_to_theta(body.mastery)
    difficulty_label, difficulty_param = select_difficulty(theta)

    log.info(
        "generating_question",
        user_id=user["id"],
        topic=body.topic,
        theta=round(theta, 3),
        difficulty=difficulty_label,
    )

    raw = await ai_service.generate_question(
        body.topic, difficulty_label, body.gaps, persona_id=body.persona_id
    )

    question = QuizQuestion(
        question=raw["question"],
        options=raw["options"],
        correct_answer=raw["correct_answer"],
        difficulty=difficulty_label,
        difficulty_param=difficulty_param,
    )

    return GenerateQuestionResponse(success=True, question=question, theta=theta)


async def _persist_evaluation(
    user_id: str,
    topic_id: str,
    is_correct: bool,
    new_mastery: float,
    db,
):
    """Background task — update mastery + streak in Supabase."""
    try:
        db.rpc("update_mastery_level", {
            "user_uuid": user_id,
            "topic_uuid": topic_id,
            "is_correct": is_correct,
        }).execute()

        if is_correct:
            db.rpc("update_user_streak", {"user_uuid": user_id}).execute()

        log.info("mastery_persisted", user_id=user_id, topic_id=topic_id, new_mastery=new_mastery)
    except Exception as e:
        log.error("mastery_persist_failed", error=str(e))


@router.post("/evaluate", response_model=EvaluateAnswerResponse)
@limiter.limit("30/minute")
async def evaluate_answer(
    request: Request,
    body: EvaluateAnswerRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db=Depends(get_supabase),
):
    """
    Evaluate a student's answer and update their IRT ability estimate.
    
    DB updates run as a background task so the API responds immediately.
    """
    log.info("evaluating_answer", user_id=user["id"], topic=body.topic)

    evaluation_raw = await ai_service.evaluate_answer(
        body.topic, body.question, body.answer, body.correct_answer
    )

    is_correct = evaluation_raw.get("is_correct", False)

    # IRT theta update
    difficulty_param = DIFFICULTY_MAP.get(
        "easy" if body.mastery < 0.33 else "intermediate" if body.mastery < 0.67 else "hard",
        0.0
    )
    new_theta = update_theta(body.theta, is_correct, difficulty_param)
    new_mastery = theta_to_mastery(new_theta)

    evaluation = EvaluationResult(
        score=evaluation_raw.get("score", 1.0 if is_correct else 0.0),
        feedback=evaluation_raw.get("feedback", ""),
        correction=evaluation_raw.get("correction", ""),
        is_correct=is_correct,
    )

    # Persist to DB asynchronously — don't block the response
    background_tasks.add_task(
        _persist_evaluation,
        user["id"], body.topic_id, is_correct, new_mastery, db,
    )

    return EvaluateAnswerResponse(
        success=True,
        evaluation=evaluation,
        new_mastery=new_mastery,
        new_theta=new_theta,
    )
