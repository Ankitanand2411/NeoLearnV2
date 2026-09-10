"""
Contract tests for the HTTP layer.

FastAPI's TestClient drives the real app (middleware, rate limiter, routers).
Three things are faked:
  * auth  – `get_current_user` dependency is overridden with a fixed user
  * DB    – `get_supabase` is overridden / patched with FakeSupabase
  * LLM   – the ai_service functions are monkeypatched to return schema objects
"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_supabase
from app.core.security import get_current_user
from app.main import app
from app.models.ai_schemas import AnswerVerdict, GeneratedQuestion, JudgeVerdict
from app.services import ai_service, persistence
from app.services.ai_service import AIServiceError
from app.services.mastery_service import DIFFICULTY_MAP, mastery_to_theta, update_theta

TEST_USER = {"id": "user-abc", "email": "test@example.com"}


@pytest.fixture
def client(fake_db, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_supabase] = lambda: fake_db
    # persistence.py calls get_supabase() directly inside background tasks
    monkeypatch.setattr(persistence, "get_supabase", lambda: fake_db)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


async def _raise_ai_error(*args, **kwargs):
    raise AIServiceError("model unavailable")


def _returning(value):
    async def _fn(*args, **kwargs):
        return value
    return _fn


# ─── Health ───────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ─── /quiz/generate ───────────────────────────────────────────────────────────

def test_generate_question_returns_question_and_theta(client, monkeypatch):
    q = GeneratedQuestion(
        question="Why is c the same in every inertial frame?",
        options=["Postulate of relativity", "Aether drag", "Doppler shift", "Mass-energy"],
        correct_answer="Postulate of relativity",
    )
    monkeypatch.setattr(ai_service, "generate_question", _returning(q))

    r = client.post("/api/v1/quiz/generate", json={"topic": "Special Relativity", "mastery": 0.9})

    assert r.status_code == 200
    body = r.json()
    assert body["question"]["correct_answer"] == "Postulate of relativity"
    assert body["question"]["difficulty"] == "hard"           # mastery 0.9 → θ 2.4 → hard
    assert body["question"]["difficulty_param"] == DIFFICULTY_MAP["hard"]
    assert body["theta"] == pytest.approx(mastery_to_theta(0.9))


def test_generate_question_returns_503_when_llm_fails(client, monkeypatch):
    monkeypatch.setattr(ai_service, "generate_question", _raise_ai_error)

    r = client.post("/api/v1/quiz/generate", json={"topic": "Special Relativity", "mastery": 0.5})

    assert r.status_code == 503
    assert "temporarily unavailable" in r.json()["detail"]


# ─── /quiz/evaluate ───────────────────────────────────────────────────────────

def test_evaluate_correct_answer_uses_question_difficulty(client, fake_db):
    theta, b = -1.0, DIFFICULTY_MAP["hard"]
    payload = {
        "topic": "Special Relativity",
        "topic_id": "topic-1",
        "question": "q",
        "answer": "Postulate of relativity",
        "correct_answer": "postulate of relativity",   # exact match → no LLM call
        "mastery": 0.33,
        "theta": theta,
        "difficulty_param": b,
    }

    r = client.post("/api/v1/quiz/evaluate", json=payload)

    assert r.status_code == 200
    body = r.json()
    assert body["evaluation"]["is_correct"] is True
    assert body["new_theta"] == pytest.approx(update_theta(theta, True, b))
    assert body["new_theta"] > theta
    # persistence ran in the background with the fake DB
    assert ("update_mastery_level", {"user_uuid": "user-abc", "topic_uuid": "topic-1", "is_correct": True}) in fake_db.rpcs
    assert ("update_user_streak", {"user_uuid": "user-abc"}) in fake_db.rpcs


def test_evaluate_wrong_answer_lowers_theta(client, monkeypatch, fake_db):
    verdict = AnswerVerdict(score=0.1, feedback="Not quite.", correction="It is c.", is_correct=False)
    monkeypatch.setattr(ai_service, "evaluate_answer", _returning(verdict))

    r = client.post(
        "/api/v1/quiz/evaluate",
        json={
            "topic": "t", "topic_id": "topic-1", "question": "q",
            "answer": "Aether drag", "correct_answer": "Postulate", "mastery": 0.5, "theta": 0.0,
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["evaluation"]["is_correct"] is False
    assert body["new_theta"] < 0.0
    # streak only advances on correct answers
    assert all(name != "update_user_streak" for name, _ in fake_db.rpcs)


def test_evaluate_returns_503_when_llm_fails(client, monkeypatch):
    monkeypatch.setattr(ai_service, "evaluate_answer", _raise_ai_error)

    r = client.post(
        "/api/v1/quiz/evaluate",
        json={"topic": "t", "topic_id": "topic-1", "question": "q", "answer": "x", "correct_answer": "y"},
    )
    assert r.status_code == 503


# ─── /chat/evaluate ───────────────────────────────────────────────────────────

def test_chat_evaluate_returns_verdict_and_persists(client, monkeypatch, fake_db):
    verdict = JudgeVerdict(score=0.75, understood=["time dilation"], gaps=["simultaneity"], reasoning="Solid.")
    monkeypatch.setattr(ai_service, "evaluate_understanding", _returning(verdict))

    r = client.post(
        "/api/v1/chat/evaluate",
        json={
            "topic": "Special Relativity",
            "topic_id": "topic-1",
            "history": [{"role": "user", "content": "Moving clocks run slow."}],
        },
    )

    assert r.status_code == 200
    assert r.json() == {
        "success": True,
        "score": 0.75,
        "understood": ["time dilation"],
        "gaps": ["simultaneity"],
        "reasoning": "Solid.",
    }
    assert "user_mastery" in fake_db.tables
    assert "user_memories" in fake_db.tables


def test_chat_evaluate_returns_503_instead_of_fake_score(client, monkeypatch, fake_db):
    monkeypatch.setattr(ai_service, "evaluate_understanding", _raise_ai_error)

    r = client.post(
        "/api/v1/chat/evaluate",
        json={"topic": "t", "topic_id": "topic-1", "history": []},
    )

    assert r.status_code == 503
    assert fake_db.tables == []   # nothing was persisted


def test_protected_route_requires_auth():
    # Fresh client without the override: real dependency runs and rejects missing header.
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        r = c.post("/api/v1/quiz/generate", json={"topic": "t", "mastery": 0.5})
    assert r.status_code == 403  # HTTPBearer: no credentials
