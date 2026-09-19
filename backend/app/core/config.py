"""Foresight AI - Application Configuration Module.

Loads environment variables, handles type casting, validation, and defaults.
Never hardcodes secrets.
"""

from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base Application Settings
    PROJECT_NAME: str = "Foresight AI - Network Attack Forecasting Platform"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Server Network Binding
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Cryptographic & Authentication Secrets
    SECRET_KEY: str = "dev-insecure-secret-key-change-in-production-min32chars"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    
    # Database Settings
    # Supports SQLite (dev default) or PostgreSQL via asyncpg
    DATABASE_URL: str = "sqlite+aiosqlite:///./foresight.db"
    
    # CORS Origins (List of URLs or JSON array string)
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        import json
        return json.loads(v)

    # ML & Forecasting Configuration
    MODEL_ARTIFACTS_DIR: str = "./artifacts/models"
    CALIBRATION_ARTIFACTS_DIR: str = "./artifacts/calibration"
    CONFORMAL_ARTIFACTS_DIR: str = "./artifacts/conformal"
    SHAP_ARTIFACTS_DIR: str = "./artifacts/shap"
    ACTIVE_MODEL_VERSION: str = "v1.0.0-temporal-gbm"
    FORECAST_HORIZON_MINUTES: int = 15
    CONFORMAL_TARGET_COVERAGE: float = 0.90
    
    # Telemetry Limits & Protection
    MAX_BATCH_FLOW_RECORDS: int = 5000
    RATE_LIMIT_PER_MINUTE: int = 120
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
