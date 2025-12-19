"""Application configuration using pydantic-settings."""

import urllib.parse
from typing import Optional
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
