"""Tests for configuration."""

from coinbot_backend.config import Settings


def test_settings_defaults() -> None:
    """Test default settings values."""
    settings = Settings()
    assert settings.app_name == "Coinbot"
    assert settings.app_version == "0.1.0"
    assert settings.log_level == "INFO"
    assert settings.bot_enabled is False
    assert settings.bot_update_interval == 120
    assert settings.bot_num_positions == 4
