from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    GROQ_API_KEY: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str
    YOUTUBE_API_KEY: str
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    REDIS_URL: str | None = None

    @property
    def origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": ".env"}


settings = Settings()
