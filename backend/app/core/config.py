from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GROQ_API_KEY: str
    # Groq model for tutor, judge, question generation and grading. Groq retires
    # models (llama-3.1-8b-instant returned 404 model_not_found in Sept 2026), so
    # this is configuration, not code. Current list: https://console.groq.com/docs/models
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str
    # Postgres connection string for the LangGraph checkpointer (Supabase →
    # Settings → Database → Connection string, URI). Use the direct connection
    # or the *session* pooler (port 5432); the transaction pooler (6543) does
    # not support the prepared statements the checkpointer uses. When unset,
    # sessions are checkpointed in memory and lost on restart (dev only).
    SUPABASE_DB_URL: str | None = None
    # Checkpointer connection pool. Keep max_size small on Supabase's free tier
    # (pooler connection limits are low) and recycle idle connections before the
    # pooler drops them.
    DB_POOL_MAX_SIZE: int = 4
    DB_POOL_MAX_IDLE_SECONDS: float = 120.0
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # --- Mentor RAG (retrieval over the mentors' own public-domain writings) ---
    # Embeddings come from Gemini (Groq has no embedding models). Without a key
    # retrieval is skipped and the tutor prompt is unchanged.
    GEMINI_API_KEY: str | None = None
    MENTOR_RAG_MODE: str = "hybrid"        # hybrid | vector | off
    MENTOR_RAG_TOP_K: int = 3
    MENTOR_EMBED_MODEL: str = "gemini-embedding-001"
    MENTOR_EMBED_DIMENSIONS: int = 768

    # --- Cost estimation (USD per 1M tokens, by model) ---
    # Defaults are Groq's published list prices at the time of writing. VERIFY
    # against https://groq.com/pricing and override via env (JSON), e.g.
    # LLM_PRICE_INPUT_PER_M='{"llama-3.3-70b-versatile": 0.59}'.
    LLM_PRICE_INPUT_PER_M: dict[str, float] = {"llama-3.3-70b-versatile": 0.59, "llama-3.1-8b-instant": 0.05, "default": 0.0}
    LLM_PRICE_OUTPUT_PER_M: dict[str, float] = {"llama-3.3-70b-versatile": 0.79, "llama-3.1-8b-instant": 0.08, "default": 0.0}

    @property
    def origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    # Ignore unknown keys in .env (e.g. PYTHON_VERSION, which belongs to Render)
    # instead of refusing to start; unknown environment variables were already ignored.
    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
