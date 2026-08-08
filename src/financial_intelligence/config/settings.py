"""Production-quality typed settings with fail-closed paid-model policy."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnvironment = Literal["development", "test", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

SERVICE_NAME = "agentic-financial-intelligence"

_SECRET_FIELD_NAMES = frozenset(
    {
        "openrouter_api_key",
        "database_url",
        "redis_url",
        "alpha_vantage_api_key",
        "finnhub_api_key",
    }
)


class Settings(BaseSettings):
    """Environment-driven application settings.

    Blank optional provider URLs/keys are intentional: Phase 1 startup must
    succeed without live external services.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnvironment = Field(default="development", alias="APP_ENV")
    log_level: LogLevel = Field(default="INFO", alias="LOG_LEVEL")
    service_name: str = Field(default=SERVICE_NAME, alias="SERVICE_NAME")

    openrouter_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENROUTER_API_KEY")
    allow_paid_models: bool = Field(default=False, alias="ALLOW_PAID_MODELS")
    primary_free_model: str = Field(default="", alias="PRIMARY_FREE_MODEL")
    fallback_free_model_1: str = Field(default="", alias="FALLBACK_FREE_MODEL_1")
    fallback_free_model_2: str = Field(default="", alias="FALLBACK_FREE_MODEL_2")

    database_url: SecretStr = Field(default=SecretStr(""), alias="DATABASE_URL")
    redis_url: SecretStr = Field(default=SecretStr(""), alias="REDIS_URL")

    alpha_vantage_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="ALPHA_VANTAGE_API_KEY",
    )
    finnhub_api_key: SecretStr = Field(default=SecretStr(""), alias="FINNHUB_API_KEY")

    http_timeout_seconds: int = Field(default=30, alias="HTTP_TIMEOUT_SECONDS", ge=1, le=300)
    max_http_retries: int = Field(default=2, alias="MAX_HTTP_RETRIES", ge=0, le=10)

    market_stale_after_hours: int = Field(
        default=72,
        alias="MARKET_STALE_AFTER_HOURS",
        ge=1,
        le=8760,
    )
    market_cache_ttl_seconds: int = Field(
        default=300,
        alias="MARKET_CACHE_TTL_SECONDS",
        ge=1,
        le=86400,
    )
    market_data_live_enabled: bool = Field(
        default=False,
        alias="MARKET_DATA_LIVE_ENABLED",
    )
    market_data_primary_provider: Literal["yahoo_finance_chart", "none"] = Field(
        default="yahoo_finance_chart",
        alias="MARKET_DATA_PRIMARY_PROVIDER",
    )
    market_data_timeout_seconds: int = Field(
        default=15,
        alias="MARKET_DATA_TIMEOUT_SECONDS",
        ge=1,
        le=120,
    )
    market_data_max_response_bytes: int = Field(
        default=1_048_576,
        alias="MARKET_DATA_MAX_RESPONSE_BYTES",
        ge=1024,
        le=10_485_760,
    )
    market_data_max_retries: int = Field(
        default=2,
        alias="MARKET_DATA_MAX_RETRIES",
        ge=0,
        le=5,
    )
    market_data_history_days: int = Field(
        default=30,
        alias="MARKET_DATA_HISTORY_DAYS",
        ge=1,
        le=365,
    )

    financial_cache_ttl_seconds: int = Field(
        default=3600,
        alias="FINANCIAL_CACHE_TTL_SECONDS",
        ge=1,
        le=86400,
    )
    financial_data_live_enabled: bool = Field(
        default=False,
        alias="FINANCIAL_DATA_LIVE_ENABLED",
    )
    financial_data_primary_provider: Literal["sec_company_facts", "none"] = Field(
        default="sec_company_facts",
        alias="FINANCIAL_DATA_PRIMARY_PROVIDER",
    )
    financial_data_timeout_seconds: int = Field(
        default=15,
        alias="FINANCIAL_DATA_TIMEOUT_SECONDS",
        ge=1,
        le=120,
    )
    financial_data_max_response_bytes: int = Field(
        default=2_097_152,
        alias="FINANCIAL_DATA_MAX_RESPONSE_BYTES",
        ge=1024,
        le=10_485_760,
    )
    financial_data_max_retries: int = Field(
        default=2,
        alias="FINANCIAL_DATA_MAX_RETRIES",
        ge=0,
        le=5,
    )

    @field_validator("allow_paid_models")
    @classmethod
    def paid_models_must_remain_disabled(cls, value: bool) -> bool:
        """Fail closed: paid models are prohibited in development policy."""

        if value is True:
            msg = "ALLOW_PAID_MODELS=true is rejected; paid models are disabled"
            raise ValueError(msg)
        return False

    @model_validator(mode="after")
    def reject_duplicate_free_model_ids(self) -> Self:
        """Reject duplicate configured free-model identifiers when present."""

        configured = [
            model_id
            for model_id in (
                self.primary_free_model,
                self.fallback_free_model_1,
                self.fallback_free_model_2,
            )
            if model_id
        ]
        if len(configured) != len(set(configured)):
            msg = "configured free model IDs must be unique"
            raise ValueError(msg)
        return self

    def secret_values(self) -> dict[str, str]:
        """Return secret field values for internal redaction tests only."""

        return {
            "openrouter_api_key": self.openrouter_api_key.get_secret_value(),
            "database_url": self.database_url.get_secret_value(),
            "redis_url": self.redis_url.get_secret_value(),
            "alpha_vantage_api_key": self.alpha_vantage_api_key.get_secret_value(),
            "finnhub_api_key": self.finnhub_api_key.get_secret_value(),
        }

    def safe_log_context(self) -> dict[str, Any]:
        """Return non-secret settings suitable for structured logs."""

        payload: dict[str, Any] = {
            "app_env": self.app_env,
            "log_level": self.log_level,
            "service_name": self.service_name,
            "allow_paid_models": self.allow_paid_models,
            "primary_free_model": self.primary_free_model or None,
            "fallback_free_model_1": self.fallback_free_model_1 or None,
            "fallback_free_model_2": self.fallback_free_model_2 or None,
            "http_timeout_seconds": self.http_timeout_seconds,
            "max_http_retries": self.max_http_retries,
            "market_stale_after_hours": self.market_stale_after_hours,
            "market_cache_ttl_seconds": self.market_cache_ttl_seconds,
            "market_data_live_enabled": self.market_data_live_enabled,
            "market_data_primary_provider": self.market_data_primary_provider,
            "market_data_timeout_seconds": self.market_data_timeout_seconds,
            "market_data_max_response_bytes": self.market_data_max_response_bytes,
            "market_data_max_retries": self.market_data_max_retries,
            "market_data_history_days": self.market_data_history_days,
            "financial_cache_ttl_seconds": self.financial_cache_ttl_seconds,
            "financial_data_live_enabled": self.financial_data_live_enabled,
            "financial_data_primary_provider": self.financial_data_primary_provider,
            "financial_data_timeout_seconds": self.financial_data_timeout_seconds,
            "financial_data_max_response_bytes": self.financial_data_max_response_bytes,
            "financial_data_max_retries": self.financial_data_max_retries,
            "database_configured": bool(self.database_url.get_secret_value()),
            "redis_configured": bool(self.redis_url.get_secret_value()),
            "openrouter_key_configured": bool(self.openrouter_api_key.get_secret_value()),
            "alpha_vantage_key_configured": bool(self.alpha_vantage_api_key.get_secret_value()),
            "finnhub_key_configured": bool(self.finnhub_api_key.get_secret_value()),
        }
        for secret_name in _SECRET_FIELD_NAMES:
            assert secret_name not in payload
        return payload


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-cached settings. Prefer explicit injection in tests."""

    return Settings()
