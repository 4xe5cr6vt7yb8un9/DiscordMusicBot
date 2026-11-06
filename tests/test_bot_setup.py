from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.bot import MusicBot
from src.config import BotConfig

def test_music_bot_initialization():
    config = BotConfig(token="fake_token", prefix="!", ffmpeg_path="ffmpeg", default_volume=0.5)
    bot = MusicBot(config)
    assert bot.bot_config == config
    assert bot.command_prefix == "!"
    assert bot.intents.voice_states is True
    assert bot.intents.message_content is True

@pytest.mark.asyncio
async def test_music_bot_setup_hook():
    config = BotConfig(token="fake_token", prefix="!", ffmpeg_path="ffmpeg", default_volume=0.5)
    bot = MusicBot(config)

    with patch.object(bot, "load_extension", new_callable=AsyncMock) as mock_load, \
         patch.object(bot.tree, "sync", new_callable=AsyncMock) as mock_sync:
        await bot.setup_hook()
        mock_load.assert_called_once_with("src.cogs.music")
        mock_sync.assert_called_once()
