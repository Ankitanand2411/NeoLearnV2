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
