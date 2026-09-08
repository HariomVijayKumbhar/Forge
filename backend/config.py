import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Some dev environments set a global DEBUG env var (e.g. "release") that is not
# a boolean; drop it so it doesn't override our .env DEBUG setting.
if "DEBUG" in os.environ and str(os.environ["DEBUG"]).strip().lower() not in {
    "1", "true", "yes", "on", "0", "false", "no", "off"
}:
    del os.environ["DEBUG"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App Info
    APP_NAME: str = "Forge Autonomous Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Security & Auth
    ACCESS_PASSWORD: str = Field(default="forge-dev-secret", description="Admin access password")
    ACCESS_TOKEN_SECRET: str = Field(default="dev-super-secret-access-token-key-change-in-prod-32chars", description="JWT secret for access tokens")
    REFRESH_TOKEN_SECRET: str = Field(default="dev-super-secret-refresh-token-key-change-in-prod-32chars", description="Secret for refresh cookies")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_HOURS: int = 8
    ALLOWED_ORIGIN: str = Field(default="http://localhost:3000", description="Allowed CORS origin")

    # LLM Providers
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    LLM_PROVIDER_CHAIN: str = "claude,gemini-flash"
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENROUTER_MODEL: str = "anthropic/claude-3.5-sonnet"
    GROQ_MODEL: str = "mixtral-8x7b-32768"

    # Agent Limits
    MAX_ITERATIONS: int = 25
    RUN_TIMEOUT_SECONDS: int = 600
    CONSECUTIVE_FAILURES_LIMIT: int = 3

    # GitHub Integration
    GITHUB_TOKEN: str | None = None

    # Database Persistence (Supabase Postgres or SQLite fallback)
    DATABASE_URL: str = Field(
        default="sqlite:///forge.db",
        description="Database connection URL (e.g. Supabase Postgres pooled connection or SQLite file)"
    )
    SQLITE_PATH: str | None = None  # Backward compatibility
    ENABLE_DOCKER_SANDBOX: bool = False  # Auto-detected if Docker is available
    SANDBOX_DOCKER_IMAGE: str = "python:3.12-slim"
    SANDBOX_TEMP_ROOT: str = "./sandbox_workspaces"


settings = Settings()
