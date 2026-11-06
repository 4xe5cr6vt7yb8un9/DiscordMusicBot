from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import discord
from discord.ext import commands

from src.cogs.music import MusicCog
from src.config import BotConfig
from src.models.song import Song

@pytest.fixture
def bot_mock():
    bot = MagicMock(spec=commands.Bot)
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 999999
    return bot

@pytest.fixture
def config_mock():
    return BotConfig(
        token="test_token",
        prefix="!",
        ffmpeg_path="ffmpeg",
        default_volume=0.5,
    )

@pytest.fixture
def ctx_mock():
    ctx = MagicMock(spec=commands.Context)
    ctx.guild = MagicMock(spec=discord.Guild)
    ctx.guild.id = 12345
    ctx.guild.voice_client = None

    author = MagicMock(spec=discord.Member)
    author.voice = MagicMock()
    author.voice.channel = MagicMock(spec=discord.VoiceChannel)
    ctx.author = author

    ctx.send = AsyncMock()
    ctx.defer = AsyncMock()
    ctx.voice_client = None
    return ctx

@pytest.mark.asyncio
async def test_play_command_not_in_vc(bot_mock, config_mock, ctx_mock):
    ctx_mock.author.voice = None
    cog = MusicCog(bot_mock, config_mock)

    await cog.play.callback(cog, ctx_mock, query="never gonna give you up")
    ctx_mock.send.assert_called_once()
    assert "You must be in a voice channel" in ctx_mock.send.call_args[0][0]

@pytest.mark.asyncio
async def test_play_command_joins_vc_and_enqueues(bot_mock, config_mock, ctx_mock):
    cog = MusicCog(bot_mock, config_mock)

    mock_vc = MagicMock(spec=discord.VoiceClient)
    ctx_mock.author.voice.channel.connect = AsyncMock(return_value=mock_vc)

    mock_song = Song(
        title="Test Song",
        webpage_url="https://youtube.com/watch?v=1",
        stream_url="https://stream.url",
        duration=180,
        uploader="Artist",
        thumbnail_url=None,
        requester_name="Author",
        requester_id=1,
    )

    with patch.object(cog.extractor, "extract_song", new_callable=AsyncMock, return_value=mock_song), \
         patch("src.cogs.music.GuildMusicPlayer") as mock_player_cls:
        
        mock_player_instance = MagicMock()
        mock_player_instance.enqueue = AsyncMock()
        mock_player_instance.is_playing = True
        mock_player_instance.current_song = None
        mock_player_cls.return_value = mock_player_instance

        await cog.play.callback(cog, ctx_mock, query="https://youtube.com/watch?v=1")

        ctx_mock.defer.assert_called_once()
        mock_player_instance.enqueue.assert_called_once_with(mock_song)
        ctx_mock.send.assert_called_once()
        _, kwargs = ctx_mock.send.call_args
        assert "embed" in kwargs
