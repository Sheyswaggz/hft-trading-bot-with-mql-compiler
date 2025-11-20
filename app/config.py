"""Application configuration using Pydantic Settings.

This module provides type-safe configuration management for the HFT Trading Bot,
loading settings from environment variables and .env files with validation.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support.

    All settings can be overridden via environment variables or .env file.
    Follows the twelve-factor app methodology for configuration management.
    """

    APP_NAME: str = Field(
        default="HFT Trading Bot",
        description="Application name for logging and monitoring",
    )
    VERSION: str = Field(
        default="0.1.0",
        description="Application version for API documentation",
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode with verbose logging and error details",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection string: postgresql://user:pass@host:port/db",
    )
    REDIS_URL: str = Field(
        ...,
        description="Redis connection string: redis://host:port/db",
    )
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins for frontend access",
    )
    MAX_POSITION_SIZE: int = Field(
        default=10000,
        description="Maximum position size for risk management",
        gt=0,
    )
    TIMEFRAME: str = Field(
        default="5m",
        description="Trading timeframe for market data aggregation",
    )
    ENABLE_BACKTESTING: bool = Field(
        default=False,
        description="Enable backtesting mode for strategy validation",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses lru_cache to ensure settings are loaded only once and reused
    across the application lifecycle for performance optimization.

    Returns:
        Settings: Validated application settings instance

    Raises:
        ValidationError: If required environment variables are missing or invalid
    """
    return Settings()