from pydantic import BaseModel
from typing import Optional, List


# ─── Quiz Schemas ────────────────────────────────────────────────────────────

class GenerateQuestionRequest(BaseModel):
    topic: str
    mastery: float = 0.0          # 0.0 – 1.0
    topic_id: Optional[str] = None
    persona_id: Optional[str] = None   # historical mentor persona
    gaps: Optional[List[str]] = None


class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    difficulty: str               # easy | intermediate | hard
    difficulty_param: float       # IRT difficulty parameter (-3 to +3)


class GenerateQuestionResponse(BaseModel):
    success: bool
    question: QuizQuestion
    theta: float                  # current student ability estimate


class EvaluateAnswerRequest(BaseModel):
    topic: str
    topic_id: str
    question: str
    answer: str
    correct_answer: str
    mastery: float = 0.0
    theta: float = 0.0            # student's current ability estimate


class EvaluationResult(BaseModel):
    score: float
    feedback: str
    correction: str
    is_correct: bool


class EvaluateAnswerResponse(BaseModel):
    success: bool
    evaluation: EvaluationResult
    new_mastery: float
    new_theta: float              # updated IRT ability estimate


# ─── Chat Schemas ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    topic: str
    topic_id: Optional[str] = None
    mastery: float = 0.0
    persona_id: Optional[str] = None   # historical mentor persona (e.g. 'einstein', 'feynman')
    history: List[dict] = []           # [{"role": "user"/"assistant", "content": "..."}]


# ─── Content Schemas ──────────────────────────────────────────────────────────

class ContentRequest(BaseModel):
    topic: str
    content_level: str = "beginner"
    preferences: str = ""


class ContentResponse(BaseModel):
    success: bool
    content: str


# ─── Analytics Schemas ────────────────────────────────────────────────────────

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


# ─── Chat Evaluation Schemas ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatEvaluateRequest(BaseModel):
    topic: str
    topic_id: str
    history: List[ChatMessage]


class ChatEvaluateResponse(BaseModel):
    success: bool
    score: float
    understood: List[str]
    gaps: List[str]
    reasoning: str

