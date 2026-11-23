"""
Application Configuration
-------------------------
Loads configuration settings from the `.env` file using Pydantic Settings.
Keeps sensitive keys, database URLs, and environment variables centralized and safe.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for backend (resolves where the .env file is located)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Application Settings schema with values automatically read from .env file.
    """
    # General Application
    PROJECT_NAME: str = "Vehicle Fuel & Mileage Tracking"
    API_PREFIX: str = "/api"

    # Security & JWT Tokens
    SECRET_KEY: str = "default_secret_key_change_in_env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Database
    DATABASE_URL: str = "sqlite:///./fuel_tracker.db"

    # Static photo uploads
    UPLOAD_DIR: str = "./uploads"

    # Geofencing configurations
    DEFAULT_GEOFENCE_RADIUS_METERS: float = 100.0
    MAX_ALLOWED_GPS_ACCURACY_METERS: float = 50.0

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Singleton instance of settings accessible across the entire application
settings = Settings()
