from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_legacy_routes_are_gone():
    with TestClient(app) as c:
        assert c.post("/api/v1/chat", json={}).status_code == 404
        assert c.post("/api/v1/quiz/generate", json={}).status_code == 404
