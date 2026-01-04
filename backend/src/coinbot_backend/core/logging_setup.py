"""Logging configuration for the trading bot application."""

import logging

from coinbot_backend.config import settings
from coinbot_backend.services.s3_storage import S3LogHandler, get_s3_storage


class ShortNameFormatter(logging.Formatter):
    """Formatter that shows only the module name instead of full path."""

    def format(self, record: logging.LogRecord) -> str:
        # Extract just the module name from the full path
        # e.g., "coinbot_backend.services.bitvavo_client" -> "bitvavo_client"
        if "." in record.name:
            record.name = record.name.split(".")[-1]
        return super().format(record)


def setup_logging(logger_name: str | None = None, run_folder: str | None = None) -> logging.Logger:
    """
    Configure logging to output to console, rotating file, and S3.

    Args:
        logger_name: Name for the logger. If None, uses the calling module's name.
        run_folder: Run folder path for S3 logs (e.g., "runs/20260103_1010/").
                   If None, generates timestamp-based folder.

    Returns:
        Configured logger instance.
    """
    log_format = "%(asctime)s - %(name)-20s - %(levelname)-8s - %(message)s"
    log_level = getattr(logging, settings.log_level.upper())

    # Create logger (use provided name or default to calling module)
    logger = logging.getLogger(logger_name) if logger_name else logging.getLogger(__name__)
    logger.setLevel(log_level)

    # Clear existing handlers to prevent Lambda warm-start issues
    # In Lambda, the same container may be reused across invocations with different run_folders
    # We must recreate handlers to ensure each run logs to its own S3 file
    if logger.handlers:
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    # Console handler (stdout/stderr)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ShortNameFormatter(log_format))
    logger.addHandler(console_handler)

    # S3 handler (upload logs to S3)
    if settings.s3_enable_log_upload:
        log_key = f"{run_folder}logs.txt"
        s3_storage = get_s3_storage()
        s3_handler = S3LogHandler(
            s3_storage=s3_storage,
            log_key=log_key,
            max_buffer_size=settings.s3_log_buffer_size,
        )
        s3_handler.setLevel(log_level)
        s3_handler.setFormatter(ShortNameFormatter(log_format))
        logger.addHandler(s3_handler)

        logger.debug(f"S3 logging enabled: s3://{settings.s3_bucket_name}/{log_key}")

    return logger
