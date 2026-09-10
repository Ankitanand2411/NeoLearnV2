from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GROQ_API_KEY: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str
    # Postgres connection string for the LangGraph checkpointer (Supabase →
    # Settings → Database → Connection string, URI). Use the direct connection
    # or the *session* pooler (port 5432); the transaction pooler (6543) does
    # not support the prepared statements the checkpointer uses. When unset,
    # sessions are checkpointed in memory and lost on restart (dev only).
    SUPABASE_DB_URL: str | None = None
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
    # Defaults are Groq's published llama-3.1-8b-instant list prices at the time
    # of writing. VERIFY against https://groq.com/pricing and override via env
    # (JSON), e.g. LLM_PRICE_INPUT_PER_M='{"llama-3.1-8b-instant": 0.05}'.
    LLM_PRICE_INPUT_PER_M: dict[str, float] = {"llama-3.1-8b-instant": 0.05, "default": 0.0}
    LLM_PRICE_OUTPUT_PER_M: dict[str, float] = {"llama-3.1-8b-instant": 0.08, "default": 0.0}

    @property
    def origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": ".env"}


settings = Settings()
