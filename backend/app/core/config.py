import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://filterjobs:filterjobs_dev@localhost:5432/filterjobs",
    )

    # LLM: Anthropic Claude API
    # Set ANTHROPIC_API_KEY to your Anthropic API key (from console.anthropic.com).
    # Optionally override ANTHROPIC_MODEL (default: claude-opus-4-6).
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

    # Cost guardrail: max jobs processed per LLM batch call (analyze / parse).
    # Raise via MAX_BATCH_JOBS env var when you need to process more.
    MAX_BATCH_JOBS: int = int(os.getenv("MAX_BATCH_JOBS", "25"))

    # App
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "5000"))


settings = Settings()