"""Application Configuration Module.

Loads and validates environment variables using Pydantic Settings.
Strictly ensures secrets are never hardcoded in source code.
"""

from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment or .env file."""

    # Server Settings
    api_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Data Storage Root
    data_dir: Path = Path(__file__).resolve().parent.parent.parent / "data"

    # Gemini API Credentials (Google AI Studio)
    gemini_api_key: str = ""
    gemini_model_name: str = "gemini-3.7-flash"

    # Google Earth Engine Credentials
    gee_project_id: str = ""
    gee_service_account_email: str = ""
    gee_private_key_path: str = ""

    # External APIs
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    overpass_api_url: str = "https://overpass-api.de/api/interpreter"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton instance."""
    return Settings()
