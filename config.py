from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # ── Ollama (local, no API key needed) ──────────────────────────────────
    ollama_base_url: str = Field(
        alias="OLLAMA_BASE_URL", default="http://localhost:11434"
    )

    # ── Model selection (Ollama model tag) ─────────────────────────────────
    queries_model: str = Field(alias="QUERIES_MODEL", default="gemma3:12b")
    userstory_model: str = Field(alias="USERSTORY_MODEL", default="gemma3:12b")
    insight_model: str = Field(alias="INSIGHT_MODEL", default="gemma3:12b")

    # ── Generation hyperparameters ─────────────────────────────────────────
    temperature: float = Field(alias="TEMPERATURE", default=0.3)
    max_tokens: int = Field(alias="MAX_TOKENS", default=2048)
    top_p: float = Field(alias="TOP_P", default=0.9)

    # ── Service security ───────────────────────────────────────────────────
    service_api_key: str = Field(alias="SERVICE_API_KEY", default="change-me-secret")

    # ── CORS ───────────────────────────────────────────────────────────────
    allowed_origin: str = Field(alias="ALLOWED_ORIGIN", default="http://localhost:8000")

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
