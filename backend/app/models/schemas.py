"""
API schemas still served by the backend.

The learning session (tutor → judge → quiz) is defined in app/api/v1/session.py
with its own request models; the structured LLM output schemas live in
app/models/ai_schemas.py.
"""

from typing import Optional

from pydantic import BaseModel


class LearningInsights(BaseModel):
    total_topics_attempted: int
    avg_mastery: float
    strongest_topic: Optional[str]
    weakest_topic: Optional[str]
    current_streak: int
    longest_streak: int
    total_questions: int
    accuracy_rate: float
    recommendation: str
