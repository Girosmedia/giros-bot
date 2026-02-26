"""Configuración de la aplicación usando pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM
    google_api_key: str = Field(default="", description="Google Gemini API Key")

    # Tavily Search
    tavily_api_key: str = Field(default="", description="Tavily Search API Key (market context)")

    # GitHub
    github_token: str = Field(default="", description="GitHub Personal Access Token")
    github_repo_owner: str = Field(default="girosmedia")
    github_repo_name: str = Field(default="girosmedia-web-new")

    # Webhooks RRSS
    social_webhook_url: str = Field(default="", description="Webhook URL para distribución social")

    # App
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton lazy de Settings. Cargado una sola vez desde .env."""
    return Settings()


# Alias para compatibilidad directa
settings = get_settings()
