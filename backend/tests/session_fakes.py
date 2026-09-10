"""Fakes shared by the graph and session-route tests."""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app.models.ai_schemas import AnswerVerdict, GeneratedQuestion, JudgeVerdict
from app.services import ai_service, persistence

TUTOR_REPLIES = [
    "Interesting. What do you think happens to a clock on a fast train?",
    "Good. And who measures the longer interval, the passenger or the platform?",
    "Precisely. So which frame is 'correct'?",
    "Exactly, neither. That is the heart of it.",
    "Let us test that.",
]

VERDICT = JudgeVerdict(score=0.7, understood=["time dilation"], gaps=["simultaneity"], reasoning="Solid grasp.")

OPTIONS = ["Postulate of relativity", "Aether drag", "Doppler shift", "Mass-energy"]


def make_question(i: int) -> GeneratedQuestion:
    return GeneratedQuestion(question=f"Question {i}: why is c invariant?", options=OPTIONS, correct_answer=OPTIONS[0])


class FakePersistence:
    def __init__(self):
        self.evaluations: list[dict] = []
        self.quiz_answers: list[bool] = []
        self.memory = "Last time: confused simultaneity with time dilation."

    async def fetch_past_memory(self, user_id, topic_id):
        return self.memory

    async def persist_evaluation(self, user_id, topic_id, score, history, eval_result):
        self.evaluations.append({"user_id": user_id, "topic_id": topic_id, "score": score, "turns": len(history)})

    async def persist_quiz_answer(self, user_id, topic_id, is_correct):
        self.quiz_answers.append(is_correct)


def install_fakes(monkeypatch, *, replies=None, judge_error: Exception | None = None, question_error: Exception | None = None):
    """Wire fake LLM + persistence into the modules the graph nodes import."""
    fake_llm = GenericFakeChatModel(messages=iter([AIMessage(content=r) for r in (replies or TUTOR_REPLIES)]))
    monkeypatch.setattr(ai_service, "_make_llm", lambda temperature=0.7: fake_llm)
    monkeypatch.setattr(ai_service, "get_topic_context", lambda topic: {
        "description": "d", "explanation": "e", "key_takeaway": "k", "mentor_id": "einstein", "id": "topic-1",
    })

    judge_calls = {"n": 0}

    async def evaluate_understanding(topic, history, persona_id=None):
        judge_calls["n"] += 1
        if judge_error and judge_calls["n"] == 1:
            raise judge_error
        return VERDICT

    question_counter = {"n": 0}

    async def generate_question(topic, difficulty, gaps=None, persona_id=None):
        question_counter["n"] += 1
        if question_error and question_counter["n"] == 1:
            raise question_error
        return make_question(question_counter["n"])

    async def evaluate_answer(topic, question, answer, correct_answer):
        correct = answer.strip().lower() == correct_answer.strip().lower()
        return AnswerVerdict(
            score=1.0 if correct else 0.0,
            feedback="Correct." if correct else "Not quite.",
            correction="No correction needed." if correct else f"The answer is {correct_answer}.",
            is_correct=correct,
        )

    monkeypatch.setattr(ai_service, "evaluate_understanding", evaluate_understanding)
    monkeypatch.setattr(ai_service, "generate_question", generate_question)
    monkeypatch.setattr(ai_service, "evaluate_answer", evaluate_answer)

    fake_persistence = FakePersistence()
    monkeypatch.setattr(persistence, "fetch_past_memory", fake_persistence.fetch_past_memory)
    monkeypatch.setattr(persistence, "persist_evaluation", fake_persistence.persist_evaluation)
    monkeypatch.setattr(persistence, "persist_quiz_answer", fake_persistence.persist_quiz_answer)
    return fake_persistence
