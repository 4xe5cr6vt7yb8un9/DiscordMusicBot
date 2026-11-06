"""Configuration loader for the Discord Music Bot."""
from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

from src.errors import ConfigurationError

@dataclass(slots=True, frozen=True)
class BotConfig:
    token: str
    prefix: str = "!"
    ffmpeg_path: str = "ffmpeg"
    default_volume: float = 0.5

    @classmethod
    def load_from_env(cls, env_path: str | None = None) -> BotConfig:
        """Load bot configuration from environment variables or .env file."""
        load_dotenv(dotenv_path=env_path)
        token = os.getenv("DISCORD_TOKEN")
        if not token or not token.strip():
            raise ConfigurationError(
                "DISCORD_TOKEN environment variable is missing or empty. "
                "Please configure it in your .env file."
            )

        prefix = os.getenv("COMMAND_PREFIX", "!")
        ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
        raw_volume = os.getenv("DEFAULT_VOLUME", "0.5")

        try:
            default_volume = float(raw_volume)
        except ValueError:
            default_volume = 0.5

        return cls(
            token=token.strip(),
            prefix=prefix.strip() or "!",
            ffmpeg_path=ffmpeg_path.strip() or "ffmpeg",
            default_volume=max(0.0, min(default_volume, 2.0)),
        )
