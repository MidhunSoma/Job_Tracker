from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class DatabaseSettings(BaseModel):
    """Database configuration settings."""
    url: str = Field(
        default=f"sqlite:///{PROJECT_ROOT}/data/tracker.db",
        description="SQLAlchemy database connection URL"
    )


class LLMSettings(BaseModel):
    """LLM configuration settings."""
    provider: str = Field(
        default="openai",
        description="Swappable LLM provider (openai, gemini, anthropic)"
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="LLM model name to execute classification/extraction"
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API authentication key"
    )
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Gemini API authentication key"
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API authentication key"
    )


class GmailSettings(BaseModel):
    """Google OAuth2 and Gmail API configuration settings."""
    client_id: Optional[str] = Field(
        default=None,
        description="Google OAuth Client ID"
    )
    client_secret: Optional[str] = Field(
        default=None,
        description="Google OAuth Client Secret"
    )
    redirect_uri: str = Field(
        default="http://localhost:8000/api/auth/callback",
        description="Google OAuth redirect URI callback"
    )
    token_path: Path = Field(
        default=PROJECT_ROOT / "data" / "token.json",
        description="Path to local Google credentials token file"
    )
    history_days: int = Field(
        default=30,
        description="Days of email inbox history to process on first run"
    )


class ExportSettings(BaseModel):
    """Excel export configuration settings."""
    excel_path: Path = Field(
        default=PROJECT_ROOT / "exports" / "job_applications.xlsx",
        description="Local path where Excel report sheet will be synchronized"
    )


class SchedulerSettings(BaseModel):
    """Background execution scheduler settings."""
    interval_minutes: int = Field(
        default=60,
        description="Cron scheduling execute frequency in minutes"
    )


class Settings(BaseSettings):
    """Master application configuration settings."""
    project_root: Path = PROJECT_ROOT
    log_file_path: Path = Field(
        default=PROJECT_ROOT / "logs" / "agent.log",
        description="Path to output structured log file"
    )
    
    # Nested configurations
    db: DatabaseSettings = DatabaseSettings()
    llm: LLMSettings = LLMSettings()
    gmail: GmailSettings = GmailSettings()
    export: ExportSettings = ExportSettings()
    scheduler: SchedulerSettings = SchedulerSettings()

    fuzzy_match_threshold: float = Field(
        default=85.0,
        description="Fuzzy similarity score threshold (0-100) for duplicate application matching"
    )

    # Allow nested overrides via environment variables using double-underscore: db__url, llm__openai_api_key, etc.
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )


settings = Settings()
