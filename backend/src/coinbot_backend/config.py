"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from coinbot_backend import __version__


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "Coinbot"
    app_version: str = __version__
    log_level: str = "INFO"
    show_loading_bars: bool = False

    # Bitvavo API
    bitvavo_api_key: str = ""
    bitvavo_api_secret: str = ""
    bitvavo_rest_url: str = "https://api.bitvavo.com/v2"
    bitvavo_ws_url: str = "wss://ws.bitvavo.com/v2/"
    bitvavo_access_window: int = 10000

    # AWS S3 Storage
    # Note: AWS credentials are handled automatically via boto3's credential chain
    # (AWS CLI config, environment variables, IAM roles, etc.)
    aws_region: str = "eu-central-1"  # AWS region for S3 bucket
    s3_bucket_name: str = "coinbot-eu-central-1"  # S3 bucket name for storing bot data
    s3_positions_key: str = "positions.json"  # S3 key for positions file
    s3_trades_key: str = "trades.json"  # S3 key for trades file
    s3_enable_log_upload: bool = True  # Enable uploading logs to S3
    s3_run_key_prefix: str = "runs/"  # S3 key prefix for run folders (logs + charts)
    s3_log_buffer_size: int = 50  # Number of log records to buffer before uploading

    # Generic Bot Configuration
    bot_enabled: bool = True  # Gernade pin
    bot_dry_run: bool = True  # Paper trading mode - no real orders placed
    bot_dry_run_initial_balance: float = 1000.0  # Starting EUR balance for dry-run mode
    bot_dry_run_fee_rate: float = 0.0030  # Bitvavo taker fee: 0.25% (market orders)(+0.5 slippage)
    bot_num_positions: int = 5  # Max number of open positions at any time
    bot_max_allocation_percent: float = 5.0  # % of available funds to use for trading
    bot_min_position_size: float = 5.0  # Minimum amount tradeable in euro
    bot_volume_limit: int = 1000000  # Don't do trades on symbols with small 24h volume
    bot_min_growth_24h: float = -10.0  # Minimum 24h growth % (negative allows dips for mean reversion)
    bot_trailing_stop_loss_pct: float = 8.0  # Sell if price drops this % from ATH since purchase

    # Strategy Configuration
    bot_entry_min_confidence: float = 0.60  # Minimum confidence for opening new positions
    bot_exit_min_confidence: float = 0.65  # Minimum confidence for closing positions
    bot_analysis_time_resolution: str = "1h"  # Time resolution for technical analysis
    bot_analysis_time_span: str = "2w"  # Time span for historical data (2w @ 1h = 336 candles)
    bot_min_candles_required: int = 200  # Minimum candles needed for analysis
    bot_buy_delay_seconds: float = 1.0  # Delay between consecutive buy orders

    # API Rate Limiting
    bitvavo_rate_limit_threshold: int = 100  # Minimum remaining calls before waiting
    bitvavo_rate_limit_reset_seconds: int = 60  # Time to wait for rate limit reset


settings = Settings()
