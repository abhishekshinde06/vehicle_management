"""
Application Configuration
-------------------------
Loads configuration settings from the `.env` file using Pydantic Settings.
Keeps sensitive keys, database URLs, and environment variables centralized and safe.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for backend (resolves where the .env file is located)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

# Explicitly load .env file into environment
load_dotenv(dotenv_path=ENV_PATH)


class Settings(BaseSettings):
    """
    Application Settings schema with values read from .env file.
    """
    # General Application
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Vehicle Fuel & Mileage Tracking")
    API_PREFIX: str = os.getenv("API_PREFIX", "/api")

    # Security & JWT Tokens
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default_secret_key_change_in_env")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL"
    )

    # Static photo uploads
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

    # Geofencing configurations
    DEFAULT_GEOFENCE_RADIUS_METERS: float = float(os.getenv("DEFAULT_GEOFENCE_RADIUS_METERS", "100.0"))
    MAX_ALLOWED_GPS_ACCURACY_METERS: float = float(os.getenv("MAX_ALLOWED_GPS_ACCURACY_METERS", "50.0"))

    # AWS S3 Storage
    USE_S3: bool = os.getenv("USE_S3", "false").lower() in ("true", "1", "yes")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-southeast-2")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "transporter-fleet-fuel-bucket")

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Singleton instance of settings accessible across the entire application
settings = Settings()
