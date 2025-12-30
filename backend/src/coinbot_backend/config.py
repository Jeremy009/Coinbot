"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "Coinbot"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    # Bitvavo API
    bitvavo_api_key: str = ""
    bitvavo_api_secret: str = ""
    bitvavo_rest_url: str = "https://api.bitvavo.com/v2"
    bitvavo_ws_url: str = "wss://ws.bitvavo.com/v2/"
    bitvavo_access_window: int = 10000

    # Trading Bot Configuration
    bot_enabled: bool = False
    bot_update_interval: int = 120  # minutes
    bot_num_positions: int = 4
    bot_volume_limit: float = 250000.0
    bot_macd_timeresolution: str = "8h"
    bot_macd_short_period: int = 12
    bot_macd_long_period: int = 39
    bot_macd_signal_period: int = 9
    bot_taker_fee_percent: float = 0.25


settings = Settings()
