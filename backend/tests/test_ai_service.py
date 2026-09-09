"""
Tests for structured LLM outputs.

No network: `_structured_llm` (the seam that builds the Groq runnable) is
replaced with a fake whose `.ainvoke` returns pre-programmed results or raises,
so we can exercise the retry/repair loop and the failure path deterministically.
"""

import pytest
from pydantic import ValidationError

from app.models.ai_schemas import AnswerVerdict, GeneratedQuestion, JudgeVerdict
from app.services import ai_service
from app.services.ai_service import AIServiceError

CURRICULUM = {
    "description": "Special relativity",
    "explanation": "Time dilation follows from the constancy of c.",
    "key_takeaway": "Simultaneity is relative.",
    "mentor_id": "einstein",
    "id": "topic-1",
}


class FakeStructuredLLM:
    """Stands in for `llm.with_structured_output(schema)`; replays `results` in order."""

    def __init__(self, results):
        self._results = list(results)
        self.calls: list[list] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def no_db(monkeypatch):
    monkeypatch.setattr(ai_service, "get_topic_context", lambda topic: CURRICULUM)


def install_fake(monkeypatch, results):
    fake = FakeStructuredLLM(results)
    monkeypatch.setattr(ai_service, "_structured_llm", lambda schema, temperature: fake)
    return fake


# ─── Schema validation ────────────────────────────────────────────────────────

def test_judge_verdict_rejects_out_of_range_score():
    with pytest.raises(ValidationError):
        JudgeVerdict(score=1.4, understood=[], gaps=[], reasoning="x")


def test_generated_question_requires_exactly_four_distinct_options():
    with pytest.raises(ValidationError):
        GeneratedQuestion(question="What is c?", options=["a", "b", "c"], correct_answer="a")
    with pytest.raises(ValidationError):
        GeneratedQuestion(question="What is c?", options=["a", "a", "b", "c"], correct_answer="a")


def test_generated_question_correct_answer_must_be_an_option():
    with pytest.raises(ValidationError):
        GeneratedQuestion(question="What is c?", options=["a", "b", "c", "d"], correct_answer="e")


def test_generated_question_snaps_case_mismatch_to_the_option():
    q = GeneratedQuestion(
        question="Which quantity is invariant?",
        options=["Speed of light", "Length", "Duration", "Mass"],
        correct_answer="speed of light",
    )
    assert q.correct_answer == "Speed of light"


# ─── Judge ────────────────────────────────────────────────────────────────────

async def test_judge_returns_validated_verdict(no_db, monkeypatch):
    verdict = JudgeVerdict(score=0.8, understood=["time dilation"], gaps=["simultaneity"], reasoning="Good.")
    fake = install_fake(monkeypatch, [verdict])

    result = await ai_service.evaluate_understanding(
        "Special Relativity", [{"role": "user", "content": "Clocks run slow when moving."}]
    )

    assert result is verdict
    assert len(fake.calls) == 1
    # System prompt carries the curriculum grounding.
    assert "Simultaneity is relative." in fake.calls[0][0].content


async def test_judge_retries_once_with_repair_message(no_db, monkeypatch):
    good = JudgeVerdict(score=0.6, understood=[], gaps=["frames"], reasoning="Partial.")
    fake = install_fake(monkeypatch, [ValueError("score must be <= 1"), good])

    result = await ai_service.evaluate_understanding("Special Relativity", [])

    assert result is good
    assert len(fake.calls) == 2
    # Second attempt has the repair hint appended.
    assert len(fake.calls[1]) == len(fake.calls[0]) + 1
    assert "did not match the required schema" in fake.calls[1][-1].content


async def test_judge_raises_instead_of_fabricating_a_score(no_db, monkeypatch):
    install_fake(monkeypatch, [RuntimeError("groq down"), RuntimeError("still down")])

    with pytest.raises(AIServiceError):
        await ai_service.evaluate_understanding("Special Relativity", [])


async def test_dict_result_is_coerced_into_schema(no_db, monkeypatch):
    install_fake(monkeypatch, [{"score": 0.3, "understood": [], "gaps": ["x"], "reasoning": "r"}])
    result = await ai_service.evaluate_understanding("Special Relativity", [])
    assert isinstance(result, JudgeVerdict)
    assert result.score == 0.3


# ─── Question generation ──────────────────────────────────────────────────────

async def test_generate_question_injects_gaps_and_returns_schema(monkeypatch):
    q = GeneratedQuestion(
        question="Why do moving clocks tick slower?",
        options=["Constancy of c", "Air resistance", "Gravity", "Mass increase"],
        correct_answer="Constancy of c",
    )
    fake = install_fake(monkeypatch, [q])

    result = await ai_service.generate_question(
        "Special Relativity", "hard", gaps=["light postulate"], persona_id="einstein"
    )

    assert result is q
    assert "light postulate" in fake.calls[0][0].content
    assert "Difficulty: hard" in fake.calls[0][0].content


async def test_generate_question_raises_after_repeated_failure(monkeypatch):
    install_fake(monkeypatch, [ValueError("bad"), ValueError("bad again")])
    with pytest.raises(AIServiceError):
        await ai_service.generate_question("Special Relativity", "easy")


# ─── Answer evaluation ────────────────────────────────────────────────────────

async def test_exact_match_short_circuits_the_llm(monkeypatch):
    fake = install_fake(monkeypatch, [])  # any call would IndexError

    result = await ai_service.evaluate_answer("t", "q", "  Speed of Light ", "speed of light")

    assert result.is_correct is True
    assert result.score == 1.0
    assert fake.calls == []


async def test_wrong_answer_goes_to_llm_and_returns_verdict(monkeypatch):
    verdict = AnswerVerdict(score=0.2, feedback="No.", correction="It is c.", is_correct=False)
    fake = install_fake(monkeypatch, [verdict])

    result = await ai_service.evaluate_answer("t", "q", "Mass", "Speed of light")

    assert result is verdict
    assert "Student Answer: Mass" in fake.calls[0][0].content
