"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AI
    xai_api_key: str = ""

    # LangSmith
    langsmith_api_key: str = ""
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_project: str = "trade-nexus-backend"
    langsmith_tracing: bool = True

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Lona Gateway
    lona_gateway_url: str = "https://gateway.lona.agency"
    lona_agent_id: str = "trade-nexus"
    lona_agent_name: str = "Trade Nexus Orchestrator"
    lona_agent_registration_secret: str = ""
    lona_agent_token: str = ""
    lona_token_ttl_days: int = 30

    # Live Engine
    live_engine_url: str = "https://live.lona.agency"
    platform_use_remote_execution: bool = False
    live_engine_service_api_key: str = ""
    live_engine_timeout_seconds: float = 8.0

    # Trader Data Module
    platform_use_trader_data_remote: bool = False
    trader_data_url: str = "http://localhost:8100"
    trader_data_service_api_key: str = ""
    trader_data_timeout_seconds: float = 8.0

    # Portfolio
    initial_capital: float = 100_000.0
    max_position_pct: float = 5.0
    max_drawdown_pct: float = 15.0

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
