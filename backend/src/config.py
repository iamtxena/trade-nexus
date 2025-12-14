"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AI
    xai_api_key: str = ""

    # LangSmith
    langsmith_api_key: str = ""
    langsmith_project: str = "trade-nexus-backend"
    langsmith_tracing: bool = True

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
