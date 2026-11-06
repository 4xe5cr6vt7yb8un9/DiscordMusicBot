from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import discord

from src.services.player import GuildMusicPlayer
from src.models.song import RepeatMode, Song

@pytest.fixture
def mock_voice_client():
    vc = MagicMock(spec=discord.VoiceClient)
    vc.is_connected.return_value = True
    vc.is_playing.return_value = False
    vc.is_paused.return_value = False
    vc.play = MagicMock()
    vc.pause = MagicMock()
    vc.resume = MagicMock()
    vc.stop = MagicMock()
    vc.disconnect = AsyncMock()
    return vc

@pytest.fixture
def sample_song():
    return Song(
        title="Test Song",
        webpage_url="https://youtube.com/watch?v=1",
        stream_url="https://stream.url/1",
        duration=120,
        uploader="Artist",
        thumbnail_url=None,
        requester_name="User",
        requester_id=1,
    )

@pytest.mark.asyncio
async def test_player_enqueue_and_play(mock_voice_client, sample_song):
    on_play_callback = AsyncMock()
    player = GuildMusicPlayer(
        voice_client=mock_voice_client,
        ffmpeg_path="ffmpeg",
        default_volume=0.5,
        on_track_start=on_play_callback,
    )

    with patch("src.services.ytdl.YouTubeExtractor.create_audio_source") as mock_create_src:
        mock_source = MagicMock(spec=discord.PCMVolumeTransformer)
        mock_create_src.return_value = mock_source

        await player.enqueue(sample_song)
        import asyncio
        await asyncio.sleep(0.05)

        assert player.current_song == sample_song
        mock_voice_client.play.assert_called_once()
        on_play_callback.assert_called_once_with(sample_song)

    player.destroy()

@pytest.mark.asyncio
async def test_player_pause_and_resume(mock_voice_client):
    mock_voice_client.is_playing.return_value = True
    mock_voice_client.is_paused.return_value = False

    player = GuildMusicPlayer(
        voice_client=mock_voice_client,
        ffmpeg_path="ffmpeg",
        default_volume=0.5,
    )

    assert player.pause() is True
    mock_voice_client.pause.assert_called_once()

    mock_voice_client.is_paused.return_value = True
    assert player.resume() is True
    mock_voice_client.resume.assert_called_once()

    player.destroy()

@pytest.mark.asyncio
async def test_player_skip_and_stop(mock_voice_client, sample_song):
    mock_voice_client.is_playing.return_value = True
    player = GuildMusicPlayer(
        voice_client=mock_voice_client,
        ffmpeg_path="ffmpeg",
        default_volume=0.5,
    )
    player.current_song = sample_song

    assert player.skip() is True
    assert player._skip_requested is True
    mock_voice_client.stop.assert_called_once()

    player.stop()
    assert player.current_song is None
    assert len(player.queue) == 0

    player.destroy()

def test_player_set_volume(mock_voice_client):
    player = GuildMusicPlayer(
        voice_client=mock_voice_client,
        ffmpeg_path="ffmpeg",
        default_volume=0.5,
    )
    player.set_volume(0.8)
    assert player.volume == 0.8
    player.destroy()

def test_player_repeat_modes(mock_voice_client):
    player = GuildMusicPlayer(
        voice_client=mock_voice_client,
        ffmpeg_path="ffmpeg",
        default_volume=0.5,
    )
    assert player.repeat_mode == RepeatMode.OFF

    # Test cycling
    assert player.toggle_repeat_mode() == RepeatMode.SONG
    assert player.toggle_repeat_mode() == RepeatMode.QUEUE
    assert player.toggle_repeat_mode() == RepeatMode.OFF

    # Test explicit setting
    assert player.toggle_repeat_mode("song") == RepeatMode.SONG
    assert player.toggle_repeat_mode("queue") == RepeatMode.QUEUE
    assert player.toggle_repeat_mode("off") == RepeatMode.OFF

    with pytest.raises(ValueError):
        player.toggle_repeat_mode("invalid_mode")

    player.destroy()

@pytest.mark.asyncio
async def test_player_on_error_callback(mock_voice_client, sample_song):
    on_error_callback = AsyncMock()
    player = GuildMusicPlayer(
        voice_client=mock_voice_client,
        ffmpeg_path="ffmpeg",
        default_volume=0.5,
        on_error=on_error_callback,
    )

    with patch("src.services.ytdl.YouTubeExtractor.create_audio_source", side_effect=Exception("FFmpeg missing")):
        await player.enqueue(sample_song)
        import asyncio
        await asyncio.sleep(0.05)

        on_error_callback.assert_called_once()
        args = on_error_callback.call_args[0]
        assert args[0] == sample_song
        assert "FFmpeg missing" in str(args[1])

    player.destroy()
