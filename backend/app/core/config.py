import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://filterjobs:filterjobs_dev@localhost:5432/filterjobs",
    )

    # LLM: OpenAI-compatible API (OpenAI, or open-source/local e.g. Ollama, LiteLLM, vLLM).
    # For local/open-source: set OPENAI_BASE_URL to your server (e.g. http://localhost:11434/v1),
    # OPENAI_MODEL to model name; OPENAI_API_KEY can be empty if the server does not require auth.
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY") or None
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # App
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "5000"))


settings = Settings()
