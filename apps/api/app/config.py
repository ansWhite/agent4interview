"""Environment-based application settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./insight_agent.db"
    model_provider: str = "fake"
    model_name: str = "deterministic-fake-v1"
    deepseek_api_key: str = ""
    web_search_enabled: bool = True
    web_search_fallback_coverage: float = 0.35
    web_fetch_enabled: bool = True
    max_agent_steps: int = 8
    max_tool_calls: int = 12
    max_task_seconds: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
