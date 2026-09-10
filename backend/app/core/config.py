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
    YOUTUBE_API_KEY: str | None = None  # not used by the backend; optional
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    REDIS_URL: str | None = None

    @property
    def origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": ".env"}


settings = Settings()
