"""
Server-side completion + badges (moved out of the browser) and curriculum
lookup by id. A small purpose-built Supabase fake records inserts and answers
selects per table.
"""

import pytest

from app.services import ai_service, persistence


class _Q:
    def __init__(self, db, table):
        self.db, self.table_name = db, table
        self.filters = {}
        self.op = "select"
        self.payload = None

    def select(self, *_):
        self.op = "select"
        return self

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def upsert(self, row, **kw):
        self.op, self.payload = "upsert", row
        return self

    def eq(self, k, v):
        self.filters[k] = v
        return self

    def ilike(self, k, v):
        self.filters[f"ilike:{k}"] = v
        return self

    def limit(self, n):
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        rows = self.db.tables.setdefault(self.table_name, [])
        if self.op in ("insert", "upsert"):
            rows.append(dict(self.payload))
            self.db.writes.append((self.table_name, dict(self.payload)))
            return type("R", (), {"data": [dict(self.payload)]})()
        out = [r for r in rows if all(r.get(k) == v for k, v in self.filters.items() if not k.startswith("ilike:"))]
        for k, v in self.filters.items():
            if k.startswith("ilike:"):
                needle = v.strip("%").lower()
                out = [r for r in out if needle in str(r.get(k[6:], "")).lower()]
        self.db.queries.append((self.table_name, dict(self.filters)))
        return type("R", (), {"data": out})()


class FakeDB:
    def __init__(self, tables=None):
        self.tables = {k: list(v) for k, v in (tables or {}).items()}
        self.writes, self.queries = [], []

    def table(self, name):
        return _Q(self, name)


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(persistence, "get_supabase", lambda: fake)
    monkeypatch.setattr(ai_service, "get_supabase", lambda: fake)
    return fake


# ─── Completion + badges ──────────────────────────────────────────────────────

async def test_first_completion_awards_first_steps_and_mastery_badge(db):
    result = await persistence.persist_completion("u1", "t1", 0.95)
    assert result == {"badges_awarded": ["First Steps", "Master"], "completed_topics": 1}
    assert ("user_progress", {"user_id": "u1", "topic_id": "t1"}) in db.writes
    assert [w[1]["badge_name"] for w in db.writes if w[0] == "user_badges"] == ["First Steps", "Master"]


async def test_expert_threshold_and_no_badge_below_it(db):
    db.tables["user_progress"] = [{"user_id": "u1", "topic_id": "old"}]           # not their first topic
    assert (await persistence.persist_completion("u1", "t2", 0.75))["badges_awarded"] == ["Expert"]
    assert (await persistence.persist_completion("u1", "t3", 0.5))["badges_awarded"] == []


async def test_completion_is_idempotent(db):
    await persistence.persist_completion("u1", "t1", 0.95)
    again = await persistence.persist_completion("u1", "t1", 0.95)
    assert again["badges_awarded"] == []                                            # nothing granted twice
    assert again["completed_topics"] == 1
    assert len([w for w in db.writes if w[0] == "user_progress"]) == 1              # progress row inserted once


async def test_completion_failure_is_swallowed_and_reported(monkeypatch):
    def boom():
        raise RuntimeError("supabase down")

    monkeypatch.setattr(persistence, "get_supabase", boom)
    assert await persistence.persist_completion("u1", "t1", 0.9) == {"badges_awarded": [], "completed_topics": 0}


# ─── Curriculum lookup ────────────────────────────────────────────────────────

def test_topic_context_selects_by_id_when_available(db):
    db.tables["topics"] = [
        {"id": "a", "title": "Special Relativity", "explanation": "sr", "mentor_id": "einstein"},
        {"id": "b", "title": "General Relativity", "explanation": "gr", "mentor_id": "einstein"},
    ]
    assert ai_service.get_topic_context("Relativity", topic_id="b")["explanation"] == "gr"
    assert db.queries[-1] == ("topics", {"id": "b"})


def test_topic_context_falls_back_to_title_match_without_id(db):
    db.tables["topics"] = [{"id": "a", "title": "Special Relativity", "explanation": "sr", "mentor_id": "einstein"}]
    ctx = ai_service.get_topic_context("Special Relativity")
    assert ctx["explanation"] == "sr" and ctx["id"] == "a"


def test_topic_context_default_when_missing(db):
    ctx = ai_service.get_topic_context("Nothing", topic_id="zzz")
    assert ctx["mentor_id"] == "" and "Teach the standard foundations" in ctx["explanation"]
