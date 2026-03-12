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

    # Webhooks RRSS (Legacy Make.com)
    social_webhook_url: str = Field(default="", description="Webhook URL para distribución social")

    # Meta (Facebook & Instagram)
    meta_access_token: str = Field(default="", description="Page Access Token de larga duración")
    facebook_page_id: str = Field(default="", description="ID de la página de Facebook")
    instagram_account_id: str = Field(
        default="", description="ID de la cuenta de Instagram Business"
    )

    # LinkedIn
    linkedin_client_id: str = Field(default="", description="Client ID de la App de LinkedIn")
    linkedin_client_secret: str = Field(
        default="", description="Client Secret de la App de LinkedIn"
    )
    linkedin_access_token: str = Field(default="", description="OAuth 2.0 Access Token")
    linkedin_refresh_access_token: str = Field(default="", description="OAuth 2.0 Refresh Token")
    linkedin_author_urn: str = Field(
        default="",
        description="URN del autor (ej: urn:li:organization:123456 o urn:li:person:abcde)",
    )

    # Database
    database_url: str = Field(
        default="",
        description="SQLAlchemy async connection string para PostgreSQL (postgresql+asyncpg://user:pass@host:port/dbname)",
    )

    # Cloudflare R2 (imágenes RRSS con watermark)
    r2_access_key_id: str = Field(default="", description="Access Key ID del token de API de R2")
    r2_secret_access_key: str = Field(
        default="", description="Secret Access Key del token de API de R2"
    )
    r2_endpoint_url: str = Field(
        default="",
        description="Endpoint S3-compatible de R2 (https://<account_id>.r2.cloudflarestorage.com)",
    )
    r2_bucket_name: str = Field(default="", description="Nombre del bucket de R2")

    # App
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    whatsapp_business_number: str = Field(
        default="",
        description="Número de WhatsApp Business con código de país, sin signos ni espacios (ej: 56912345678)",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton lazy de Settings. Cargado una sola vez desde .env."""
    return Settings()


# Alias para compatibilidad directa
settings = get_settings()
