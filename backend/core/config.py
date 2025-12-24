"""Application configuration using pydantic-settings."""

import re
import urllib.parse
from pathlib import Path
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Environment
    env: str = "development"

    # Supabase PostgreSQL
    supabase_db_host: str
    supabase_db_port: int = 5432
    supabase_db_name: str = "postgres"
    supabase_db_user: str = "postgres"
    supabase_db_password: str
    supabase_db_ssl: bool = True
    supabase_ca_cert_path: Optional[str] = None
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: float = 30.0
    db_pool_recycle: int = 1800
    db_pool_pre_ping: bool = True

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 0
    redis_socket_timeout: float = 5.0
    redis_connect_timeout: float = 5.0

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    # API
    api_port: int = 8000
    
    # CORS - comma-separated list of allowed origins
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    @field_validator('cors_origins')
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """Validate CORS origins are proper URLs with scheme."""
        url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
        origins = [o.strip() for o in v.split(",") if o.strip()]
        if not origins:
            raise ValueError("cors_origins must contain at least one valid origin")
        for origin in origins:
            if not url_pattern.match(origin):
                raise ValueError(f"Invalid CORS origin '{origin}': must be a valid URL with http/https scheme")
        return v
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Document Storage
    document_storage_path: str = "/data/documents"
    max_upload_size_mb: int = 50

    @field_validator('document_storage_path')
    @classmethod
    def validate_storage_path(cls, v: str) -> str:
        """Ensure document storage path is absolute."""
        path = Path(v)
        if not path.is_absolute():
            raise ValueError(f"document_storage_path must be absolute, got: {v}")
        return v

    @field_validator('max_upload_size_mb')
    @classmethod
    def validate_upload_size(cls, v: int) -> int:
        """Ensure upload size is positive and reasonable."""
        if v <= 0:
            raise ValueError(f"max_upload_size_mb must be positive, got: {v}")
        if v > 5000:
            raise ValueError(f"max_upload_size_mb exceeds maximum (5000 MB), got: {v}")
        return v

    @property
    def database_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        user = urllib.parse.quote_plus(self.supabase_db_user)
        password = urllib.parse.quote_plus(self.supabase_db_password)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.supabase_db_host}:{self.supabase_db_port}/{self.supabase_db_name}"
        )

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
