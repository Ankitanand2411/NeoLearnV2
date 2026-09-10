import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.security import get_current_user
from app.models.schemas import (
    EvaluateAnswerRequest,
    EvaluateAnswerResponse,
    EvaluationResult,
    GenerateQuestionRequest,
    GenerateQuestionResponse,
    QuizQuestion,
)
from app.services import ai_service
from app.services.ai_service import AIServiceError
from app.services.mastery_service import (
    mastery_to_theta,
    select_difficulty,
    theta_to_mastery,
    update_theta,
)
from app.services.persistence import persist_quiz_answer

router = APIRouter(prefix="/quiz", tags=["Quiz"])
limiter = Limiter(key_func=get_remote_address)
log = structlog.get_logger()

_UNAVAILABLE = "The quiz service is temporarily unavailable. Please try again in a moment."


@router.post("/generate", response_model=GenerateQuestionResponse)
@limiter.limit("20/minute")
async def generate_question(
    request: Request,
    body: GenerateQuestionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Generate an adaptive question using IRT-based difficulty selection.

    The difficulty band is the one whose b is nearest the student's ability
    estimate θ, which is where a logistic item is most informative.
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

    try:
        generated = await ai_service.generate_question(
            body.topic, difficulty_label, body.gaps, persona_id=body.persona_id
        )
    except AIServiceError as e:
        log.error("question_generation_unavailable", user_id=user["id"], error=str(e))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from e

    question = QuizQuestion(
        question=generated.question,
        options=generated.options,
        correct_answer=generated.correct_answer,
        difficulty=difficulty_label,
        difficulty_param=difficulty_param,
    )

    return GenerateQuestionResponse(success=True, question=question, theta=theta)


@router.post("/evaluate", response_model=EvaluateAnswerResponse)
@limiter.limit("30/minute")
async def evaluate_answer(
    request: Request,
    body: EvaluateAnswerRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """
    Evaluate a student's answer and update their IRT ability estimate.

    DB updates run as a background task so the API responds immediately.
    """
    log.info("evaluating_answer", user_id=user["id"], topic=body.topic)

    try:
        verdict = await ai_service.evaluate_answer(
            body.topic, body.question, body.answer, body.correct_answer
        )
    except AIServiceError as e:
        log.error("answer_evaluation_unavailable", user_id=user["id"], error=str(e))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from e

    is_correct = verdict.is_correct

    # Use the difficulty (b) of the question that was actually asked. Fall back
    # to the same θ→band mapping /generate uses, so both endpoints agree.
    if body.difficulty_param is not None:
        difficulty_param = body.difficulty_param
    else:
        _, difficulty_param = select_difficulty(body.theta)

    new_theta = update_theta(body.theta, is_correct, difficulty_param)
    new_mastery = theta_to_mastery(new_theta)

    evaluation = EvaluationResult(
        score=verdict.score,
        feedback=verdict.feedback,
        correction=verdict.correction,
        is_correct=is_correct,
    )

    background_tasks.add_task(persist_quiz_answer, user["id"], body.topic_id, is_correct)

    return EvaluateAnswerResponse(
        success=True,
        evaluation=evaluation,
        new_mastery=new_mastery,
        new_theta=new_theta,
    )
