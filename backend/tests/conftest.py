"""
Shared test setup.

`app.core.config.Settings()` is instantiated at import time and requires several
environment variables, so we set safe fake values BEFORE any `app.*` import.
Nothing here talks to Supabase, Groq or Redis: every external call is replaced
with a fake in the individual test modules.
"""

import base64
import os

# Raw key material used to sign HS256 test tokens. The setting is stored as its
# base64 form so both branches of verify_token (raw string, then base64-decoded
# bytes) can be exercised.
HS256_RAW_KEY = b"neolearn-test-signing-key-0123456789abcdef"
HS256_SECRET_SETTING = base64.b64encode(HS256_RAW_KEY).decode()

os.environ.setdefault("GROQ_API_KEY", "gsk_test_not_real")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "service-role-test-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", HS256_SECRET_SETTING)
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")

import pytest  # noqa: E402


class _Query:
    """Chainable stand-in for supabase-py's query builder. `.execute()` returns no rows."""

    def __getattr__(self, _name):
        return lambda *args, **kwargs: self

    def execute(self):
        class _Resp:
            data = []
        return _Resp()


class FakeSupabase:
    """Records calls; every query executes successfully with empty data."""

    def __init__(self):
        self.tables: list[str] = []
        self.rpcs: list[tuple[str, dict]] = []

    def table(self, name: str):
        self.tables.append(name)
        return _Query()

    def rpc(self, name: str, params: dict):
        self.rpcs.append((name, params))
        return _Query()


@pytest.fixture
def fake_db():
    return FakeSupabase()
