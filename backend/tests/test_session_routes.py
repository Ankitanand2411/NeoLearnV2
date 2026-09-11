"""
HTTP contract tests for /api/v1/session/*. The real app runs with its lifespan
(in-memory checkpointer, since SUPABASE_DB_URL is unset in tests); auth is
overridden and the LLM + persistence are faked.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import session as session_module
from app.core.security import get_current_user
from app.graph.state import MIN_STUDENT_TURNS, QUIZ_LENGTH
from app.main import app
from app.services.ai_service import AIServiceError
from tests.session_fakes import OPTIONS, TUTOR_REPLIES, install_fakes

USER = {"id": "user-abc", "email": "t@example.com"}
OTHER = {"id": "user-xyz", "email": "o@example.com"}
START = {"topic_id": "topic-1", "topic": "Special Relativity", "persona_id": "einstein", "mastery": 0.5}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(session_module.limiter, "enabled", False)
    app.dependency_overrides[get_current_user] = lambda: USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def read_sse(response):
    tokens, meta = [], []
    for line in response.iter_lines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            break
        obj = json.loads(payload)
        (tokens if "token" in obj else meta).append(obj)
    return tokens, meta


def talk(client, sid, n):
    for i in range(n):
        with client.stream("POST", f"/api/v1/session/{sid}/message", json={"message": f"msg {i}"}) as r:
            assert r.status_code == 200
            read_sse(r)


# ─── Start / get ──────────────────────────────────────────────────────────────

def test_start_returns_view_without_answer_material(client, monkeypatch):
    install_fakes(monkeypatch)
    r = client.post("/api/v1/session/start", json=START)
    assert r.status_code == 200
    v = r.json()
    assert v["phase"] == "tutor" and v["completed"] is False
    assert v["student_turns"] == 0 and v["can_evaluate"] is False
    assert len(v["messages"]) == 1 and v["messages"][0]["role"] == "assistant"   # server-seeded greeting
    assert v["question"] is None and v["verdict"] is None and v["completion"] is None
    assert v["quiz"] == {"index": 0, "total": QUIZ_LENGTH, "answers": []}
    assert len(v["session_id"]) == 32


def test_get_session_and_ownership(client, monkeypatch):
    install_fakes(monkeypatch)
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    assert client.get(f"/api/v1/session/{sid}").status_code == 200

    as_user(OTHER)
    assert client.get(f"/api/v1/session/{sid}").status_code == 404      # someone else's session is invisible
    assert client.post(f"/api/v1/session/{sid}/evaluate").status_code == 404


def test_unknown_session_is_404(client, monkeypatch):
    install_fakes(monkeypatch)
    assert client.get("/api/v1/session/deadbeef").status_code == 404


# ─── Message stream ───────────────────────────────────────────────────────────

def test_message_streams_tokens_then_done_event(client, monkeypatch):
    install_fakes(monkeypatch)
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]

    with client.stream("POST", f"/api/v1/session/{sid}/message", json={"message": "Clocks slow down when moving"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        tokens, meta = read_sse(r)

    assert "".join(t["token"] for t in tokens) == TUTOR_REPLIES[0]
    assert len(tokens) > 1                                                # actually streamed, not one blob
    assert meta == [{"done": True, "student_turns": 1, "can_evaluate": False}]

    v = client.get(f"/api/v1/session/{sid}").json()
    assert v["messages"][1:] == [
        {"role": "user", "content": "Clocks slow down when moving"},
        {"role": "assistant", "content": TUTOR_REPLIES[0]},
    ]


def test_can_evaluate_flips_after_min_turns(client, monkeypatch):
    install_fakes(monkeypatch)
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    talk(client, sid, MIN_STUDENT_TURNS)
    v = client.get(f"/api/v1/session/{sid}").json()
    assert v["student_turns"] == MIN_STUDENT_TURNS and v["can_evaluate"] is True


# ─── Evaluate ─────────────────────────────────────────────────────────────────

def test_evaluate_too_early_is_400(client, monkeypatch):
    install_fakes(monkeypatch)
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    talk(client, sid, MIN_STUDENT_TURNS - 1)
    r = client.post(f"/api/v1/session/{sid}/evaluate")
    assert r.status_code == 400
    assert str(MIN_STUDENT_TURNS) in r.json()["detail"]


def test_evaluate_returns_verdict_and_first_question(client, monkeypatch):
    install_fakes(monkeypatch)
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    talk(client, sid, MIN_STUDENT_TURNS)

    r = client.post(f"/api/v1/session/{sid}/evaluate")
    assert r.status_code == 200
    v = r.json()
    assert v["phase"] == "quiz"
    assert v["verdict"]["score"] == 0.7 and v["verdict"]["gaps"] == ["simultaneity"]
    assert v["mastery"] == 0.7
    assert v["question"]["index"] == 0 and v["question"]["options"] == OPTIONS
    assert "correct_answer" not in json.dumps(v)                          # nowhere in the payload

    # Second evaluate and further chatting are refused now.
    assert client.post(f"/api/v1/session/{sid}/evaluate").status_code == 409
    with client.stream("POST", f"/api/v1/session/{sid}/message", json={"message": "hi"}) as m:
        assert m.status_code == 409


def test_evaluate_503_when_model_fails_then_retry_succeeds(client, monkeypatch):
    install_fakes(monkeypatch, judge_error=AIServiceError("groq down"))
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    talk(client, sid, MIN_STUDENT_TURNS)

    r = client.post(f"/api/v1/session/{sid}/evaluate")
    assert r.status_code == 503
    assert client.get(f"/api/v1/session/{sid}").json()["phase"] == "tutor"   # unchanged

    assert client.post(f"/api/v1/session/{sid}/evaluate").status_code == 200  # retry


# ─── Answer ───────────────────────────────────────────────────────────────────

def test_answer_before_quiz_is_409(client, monkeypatch):
    install_fakes(monkeypatch)
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    assert client.post(f"/api/v1/session/{sid}/answer", json={"answer": "x"}).status_code == 409


def test_full_quiz_through_http(client, monkeypatch):
    install_fakes(monkeypatch)
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    talk(client, sid, MIN_STUDENT_TURNS)
    client.post(f"/api/v1/session/{sid}/evaluate")

    for i in range(QUIZ_LENGTH):
        answer = OPTIONS[0] if i != 2 else OPTIONS[3]
        r = client.post(f"/api/v1/session/{sid}/answer", json={"answer": answer})
        assert r.status_code == 200
        v = r.json()
        assert v["evaluation"]["index"] == i
        assert v["evaluation"]["is_correct"] is (i != 2)
        assert v["evaluation"]["correct_answer"] == OPTIONS[0]           # revealed after grading
        if i < QUIZ_LENGTH - 1:
            assert v["phase"] == "quiz" and v["question"]["index"] == i + 1
            assert "correct_answer" not in json.dumps(v["question"])
        else:
            assert v["phase"] == "done" and v["completed"] is True and v["question"] is None
            assert v["completion"]["badges_awarded"]                            # badges come from the server now

    assert client.post(f"/api/v1/session/{sid}/answer", json={"answer": "x"}).status_code == 409
    final = client.get(f"/api/v1/session/{sid}").json()
    assert final["quiz"]["index"] == QUIZ_LENGTH and len(final["quiz"]["answers"]) == QUIZ_LENGTH


def test_session_requires_auth():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        assert c.post("/api/v1/session/start", json=START).status_code == 403


# ─── Recovery after a mid-step failure ────────────────────────────────────────

def test_pending_step_is_visible_and_blocks_chat_until_continued(client, monkeypatch):
    install_fakes(monkeypatch, judge_error=AIServiceError("groq down"))
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    talk(client, sid, MIN_STUDENT_TURNS)
    assert client.post(f"/api/v1/session/{sid}/evaluate").status_code == 503

    v = client.get(f"/api/v1/session/{sid}").json()
    assert v["phase"] == "tutor" and v["pending_step"] == "judge"

    with client.stream("POST", f"/api/v1/session/{sid}/message", json={"message": "hello?"}) as m:
        assert m.status_code == 409                                     # finish the parked step first
        m.read()
        assert "judge" in m.json()["detail"] and "/continue" in m.json()["detail"]

    r = client.post(f"/api/v1/session/{sid}/continue")
    assert r.status_code == 200
    assert r.json()["phase"] == "quiz" and r.json()["pending_step"] is None
    assert r.json()["question"]["index"] == 0


def test_question_generation_failure_is_recoverable(client, monkeypatch):
    install_fakes(monkeypatch, question_error=AIServiceError("groq down"))
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    talk(client, sid, MIN_STUDENT_TURNS)

    assert client.post(f"/api/v1/session/{sid}/evaluate").status_code == 503   # judge ok, generation failed
    v = client.get(f"/api/v1/session/{sid}").json()
    assert v["phase"] == "quiz" and v["verdict"]["score"] == 0.7           # judge result was kept
    assert v["question"] is None and v["pending_step"] == "quiz_generate"

    r = client.post(f"/api/v1/session/{sid}/continue")
    assert r.status_code == 200 and r.json()["question"]["index"] == 0


def test_continue_is_idempotent_when_nothing_pending(client, monkeypatch):
    install_fakes(monkeypatch)
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    r = client.post(f"/api/v1/session/{sid}/continue")
    assert r.status_code == 200 and r.json()["student_turns"] == 0


# ─── Telemetry surfaces ───────────────────────────────────────────────────────

def test_session_view_accumulates_usage(client, monkeypatch):
    install_fakes(monkeypatch)
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    assert client.get(f"/api/v1/session/{sid}").json()["usage"]["llm_calls"] == 0
    talk(client, sid, 2)
    usage = client.get(f"/api/v1/session/{sid}").json()["usage"]
    assert usage["llm_calls"] == 2                     # one tutor call per turn
    assert usage["prompt_tokens"] == 0                 # fake model reports no usage; counted honestly as 0
    assert set(usage) == {"llm_calls", "prompt_tokens", "completion_tokens", "cost_usd"}


def test_metrics_endpoint_reports_routes_and_llm_purposes(client, monkeypatch):
    install_fakes(monkeypatch)
    sid = client.post("/api/v1/session/start", json=START).json()["session_id"]
    talk(client, sid, 1)

    r = client.get("/api/v1/metrics")
    assert r.status_code == 200
    snap = r.json()
    assert "tutor" in snap["llm"] and snap["llm"]["tutor"]["count"] >= 1
    assert snap["llm"]["tutor"]["p95_ms"] is not None
    assert "POST /api/v1/session/start" in snap["http"]
    assert "POST /api/v1/session/{session_id}/message" in snap["http"]       # route template, not raw path
    assert snap["llm_totals"]["calls"] >= 1
