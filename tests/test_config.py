import os
import pytest
from src.config import BotConfig
from src.errors import ConfigurationError

def test_bot_config_load_success(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "test_mock_token_12345")
    monkeypatch.setenv("COMMAND_PREFIX", "?")
    monkeypatch.setenv("FFMPEG_PATH", "custom_ffmpeg")
    monkeypatch.setenv("DEFAULT_VOLUME", "0.8")

    config = BotConfig.load_from_env()
    assert config.token == "test_mock_token_12345"
    assert config.prefix == "?"
    assert config.ffmpeg_path == "custom_ffmpeg"
    assert config.default_volume == 0.8

def test_bot_config_missing_token_raises_error(monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        BotConfig.load_from_env()
    assert "DISCORD_TOKEN" in str(exc_info.value)

def test_bot_config_defaults(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "dummy_token")
    monkeypatch.delenv("COMMAND_PREFIX", raising=False)
    monkeypatch.delenv("FFMPEG_PATH", raising=False)
    monkeypatch.delenv("DEFAULT_VOLUME", raising=False)

    config = BotConfig.load_from_env()
    assert config.token == "dummy_token"
    assert config.prefix == "!"
    assert config.ffmpeg_path == "ffmpeg"
    assert config.default_volume == 0.5
