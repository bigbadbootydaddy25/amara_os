from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded from .env, which is owner-readable only and never committed."""

    database_url: str = ""
    supabase_url: str = ""
    supabase_service_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
