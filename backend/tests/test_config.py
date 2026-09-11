"""Settings must tolerate unrelated keys in a .env file (hosting variables like PYTHON_VERSION)."""

from app.core.config import Settings


def test_unknown_env_file_keys_are_ignored(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("PYTHON_VERSION=3.12.10\nSOME_RENDER_THING=1\n")
    monkeypatch.chdir(tmp_path)
    s = Settings(_env_file=str(env))          # required fields come from the test environment
    assert s.GROQ_API_KEY                       # loaded normally
    assert not hasattr(s, "PYTHON_VERSION")    # and the stray key was dropped, not rejected
