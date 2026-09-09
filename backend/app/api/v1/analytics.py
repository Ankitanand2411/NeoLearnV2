import structlog
from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_supabase
from app.core.security import get_current_user
from app.models.schemas import LearningInsights

router = APIRouter(prefix="/analytics", tags=["Analytics"])
limiter = Limiter(key_func=get_remote_address)
log = structlog.get_logger()


@router.get("/insights", response_model=LearningInsights)
@limiter.limit("30/minute")
async def get_learning_insights(
    request: Request,
    user: dict = Depends(get_current_user),
    db=Depends(get_supabase),
):
    """
    Aggregate learning analytics for the authenticated user.
    Returns mastery stats, streak data, and an AI-derived recommendation.
    """
    user_id = user["id"]
    log.info("fetching_insights", user_id=user_id)

    # Fetch mastery data
    mastery_resp = (
        db.table("user_mastery")
        .select("mastery_level, questions_attempted, questions_correct, topic_id")
        .eq("user_id", user_id)
        .execute()
    )
    mastery_rows = mastery_resp.data or []

    # Fetch topic names for mastery rows
    topic_ids = [r["topic_id"] for r in mastery_rows]
    topic_map = {}
    if topic_ids:
        topics_resp = (
            db.table("topics")
            .select("id, title")
            .in_("id", topic_ids)
            .execute()
        )
        topic_map = {t["id"]: t["title"] for t in (topics_resp.data or [])}

    # Fetch streak
    streak_resp = (
        db.table("user_streaks")
        .select("current_streak, longest_streak")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    streak = streak_resp.data or {"current_streak": 0, "longest_streak": 0}

    # Compute aggregates
    total_attempted = sum(r["questions_attempted"] for r in mastery_rows)
    total_correct = sum(r["questions_correct"] for r in mastery_rows)
    avg_mastery = (
        sum(r["mastery_level"] for r in mastery_rows) / len(mastery_rows)
        if mastery_rows else 0.0
    )
    accuracy = total_correct / total_attempted if total_attempted > 0 else 0.0

    strongest = max(mastery_rows, key=lambda r: r["mastery_level"], default=None)
    weakest = min(mastery_rows, key=lambda r: r["mastery_level"], default=None)

    # Simple rule-based recommendation
    if avg_mastery < 0.3:
        recommendation = "Focus on foundational topics — revisit basics before moving on."
    elif avg_mastery < 0.6:
        recommendation = "Good progress! Challenge yourself with intermediate questions."
    elif accuracy < 0.5:
        recommendation = "Your accuracy needs work — slow down and review before attempting harder questions."
    else:
        recommendation = "Excellent! Push into advanced topics to reach mastery."

    return LearningInsights(
        total_topics_attempted=len(mastery_rows),
        avg_mastery=round(avg_mastery, 4),
        strongest_topic=topic_map.get(strongest["topic_id"]) if strongest else None,
        weakest_topic=topic_map.get(weakest["topic_id"]) if weakest else None,
        current_streak=streak["current_streak"],
        longest_streak=streak["longest_streak"],
        total_questions=total_attempted,
        accuracy_rate=round(accuracy, 4),
        recommendation=recommendation,
    )
