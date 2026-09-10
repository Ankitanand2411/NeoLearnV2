"""
Supabase writes shared by the legacy routes and the session graph.

Both entry points used to carry their own copy of this logic (chat.py and
quiz.py). Keeping it in one place means the graph nodes and the old endpoints
cannot drift apart, and tests can swap a single module.
"""

from datetime import datetime, timezone

import structlog

from app.core.database import get_supabase

log = structlog.get_logger()


async def persist_evaluation(user_id: str, topic_id: str, score: float, history: list, eval_result: dict) -> None:
    """Write the judge's verdict: mastery upsert + episodic memory row."""
    try:
        db = get_supabase()
        db.table("user_mastery").upsert(
            {
                "user_id": user_id,
                "topic_id": topic_id,
                "mastery_level": score,
                "last_reviewed": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="user_id,topic_id",
        ).execute()

        summary = (
            f"Session Score: {score:.2f}. Understood: {', '.join(eval_result.get('understood', []))}. "
            f"Gaps: {', '.join(eval_result.get('gaps', []))}."
        )
        db.table("user_memories").insert(
            {
                "user_id": user_id,
                "topic_id": topic_id,
                "conversation_history": history,
                "evaluation_result": eval_result,
                "memory_summary": summary,
            }
        ).execute()
        log.info("evaluation_persisted", user_id=user_id, topic_id=topic_id, score=score)
    except Exception as e:
        log.error("evaluation_persist_failed", error=str(e))


async def persist_quiz_answer(user_id: str, topic_id: str, is_correct: bool) -> None:
    """Advance mastery/streak counters for one graded quiz answer."""
    try:
        db = get_supabase()
        db.rpc("update_mastery_level", {"user_uuid": user_id, "topic_uuid": topic_id, "is_correct": is_correct}).execute()
        if is_correct:
            db.rpc("update_user_streak", {"user_uuid": user_id}).execute()
    except Exception as e:
        log.error("quiz_answer_persist_failed", error=str(e))


async def fetch_past_memory(user_id: str, topic_id: str | None) -> str | None:
    """
    Latest episodic memory summary for (user, topic), or None.

    The insert writes `memory_summary` but the original read selected a column
    named `summary`; whichever the live schema has, `select("*")` returns it and
    we take the first present. A failed read is logged and treated as "no
    memory" so the tutor still responds.
    """
    if not topic_id:
        return None
    try:
        db = get_supabase()
        res = (
            db.table("user_memories")
            .select("*")
            .eq("user_id", user_id)
            .eq("topic_id", topic_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            row = res.data[0]
            return row.get("memory_summary") or row.get("summary")
    except Exception as e:
        log.error("memory_fetch_failed", user_id=user_id, topic_id=topic_id, error=str(e))
    return None


BADGE_MASTER = 0.9
BADGE_EXPERT = 0.7


async def persist_completion(user_id: str, topic_id: str, mastery: float) -> dict:
    """
    Record a completed topic and award badges. Server-side and idempotent, so a
    client cannot grant itself badges and a retried request cannot duplicate them.

    Rules (moved verbatim from the old client code):
      'First Steps' on the user's first completed topic,
      'Master' at mastery >= 0.9, else 'Expert' at mastery >= 0.7.
    Returns {"badges_awarded": [...], "completed_topics": n}.
    """
    awarded: list[str] = []
    completed = 0
    try:
        db = get_supabase()
        existing = db.table("user_progress").select("topic_id").eq("user_id", user_id).execute().data or []
        if not any(r.get("topic_id") == topic_id for r in existing):
            db.table("user_progress").insert({"user_id": user_id, "topic_id": topic_id}).execute()
            existing.append({"topic_id": topic_id})
        completed = len(existing)

        wanted = []
        if completed == 1:
            wanted.append("First Steps")
        if mastery >= BADGE_MASTER:
            wanted.append("Master")
        elif mastery >= BADGE_EXPERT:
            wanted.append("Expert")

        if wanted:
            have = {r.get("badge_name") for r in (db.table("user_badges").select("badge_name").eq("user_id", user_id).execute().data or [])}
            for badge in wanted:
                if badge not in have:
                    db.table("user_badges").insert({"user_id": user_id, "badge_name": badge}).execute()
                    awarded.append(badge)
        log.info("completion_persisted", user_id=user_id, topic_id=topic_id, badges=awarded, completed=completed)
    except Exception as e:
        log.error("completion_persist_failed", user_id=user_id, topic_id=topic_id, error=str(e))
    return {"badges_awarded": awarded, "completed_topics": completed}
