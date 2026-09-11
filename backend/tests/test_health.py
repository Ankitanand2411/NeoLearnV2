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


async def test_postgres_checkpointer_uses_a_checked_pool(monkeypatch):
    """The lifespan must build a health-checked connection pool, not a single connection."""
    import app.main as main_module
    from app.core.config import settings

    created = {}

    class FakePool:
        def __init__(self, **kwargs):
            created.update(kwargs)
            self.opened = self.closed = False

        async def open(self, wait=True, timeout=None):
            self.opened = True

        async def close(self):
            self.closed = True

    from langgraph.checkpoint.memory import InMemorySaver

    class FakeSaver(InMemorySaver):          # a real saver type, so build_graph accepts it
        def __init__(self, conn):
            super().__init__()
            created["saver_conn"] = conn

        async def setup(self):
            created["setup"] = True

    import langgraph.checkpoint.postgres.aio as aio_mod
    import psycopg_pool

    monkeypatch.setattr(settings, "SUPABASE_DB_URL", "postgresql://u:p@pooler.example:5432/postgres")
    monkeypatch.setattr(psycopg_pool, "AsyncConnectionPool", FakePool)
    FakePool.check_connection = staticmethod(lambda conn: None)
    monkeypatch.setattr(aio_mod, "AsyncPostgresSaver", FakeSaver)

    async with main_module.lifespan(main_module.app):
        pool = created["saver_conn"]
        assert isinstance(pool, FakePool) and pool.opened
        assert created["setup"] is True
        assert created["check"] is FakePool.check_connection          # dead connections are detected
        assert created["max_idle"] == settings.DB_POOL_MAX_IDLE_SECONDS
        assert created["kwargs"]["autocommit"] is True and created["kwargs"]["prepare_threshold"] == 0
        assert created["min_size"] >= 1 and created["max_size"] == settings.DB_POOL_MAX_SIZE
    assert pool.closed                                                 # released on shutdown
