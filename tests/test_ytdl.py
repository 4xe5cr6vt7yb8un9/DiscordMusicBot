from unittest.mock import MagicMock, patch
import pytest
import discord

from src.services.ytdl import YouTubeExtractor
from src.errors import AudioExtractionError
from src.models.song import Song

@pytest.fixture
def mock_member():
    member = MagicMock(spec=discord.Member)
    member.display_name = "MusicLover"
    member.id = 123456789
    return member

@pytest.mark.asyncio
async def test_extract_song_direct_url_success(mock_member):
    extractor = YouTubeExtractor()
    mock_info = {
        "title": "Synthwave Chill Beats",
        "webpage_url": "https://www.youtube.com/watch?v=mock123",
        "url": "https://googlevideo.com/videoplayback/directstream",
        "duration": 240,
        "uploader": "Lofi Chill Records",
        "thumbnail": "https://img.youtube.com/vi/mock123/hqdefault.jpg",
    }

    with patch.object(extractor, "_extract_info_sync", return_value=mock_info):
        song = await extractor.extract_song("https://www.youtube.com/watch?v=mock123", mock_member)

    assert isinstance(song, Song)
    assert song.title == "Synthwave Chill Beats"
    assert song.webpage_url == "https://www.youtube.com/watch?v=mock123"
    assert song.stream_url == "https://googlevideo.com/videoplayback/directstream"
    assert song.duration == 240
    assert song.uploader == "Lofi Chill Records"
    assert song.thumbnail_url == "https://img.youtube.com/vi/mock123/hqdefault.jpg"
    assert song.requester_name == "MusicLover"
    assert song.requester_id == 123456789

@pytest.mark.asyncio
async def test_extract_song_search_query_success(mock_member):
    extractor = YouTubeExtractor()
    mock_search_info = {
        "_type": "playlist",
        "entries": [
            {
                "title": "First Search Result",
                "webpage_url": "https://www.youtube.com/watch?v=search1",
                "url": "https://googlevideo.com/videoplayback/searchstream",
                "duration": 195,
                "uploader": "Search Artist",
                "thumbnail": "https://img.youtube.com/vi/search1/hqdefault.jpg",
            }
        ]
    }

    with patch.object(extractor, "_extract_info_sync", return_value=mock_search_info):
        song = await extractor.extract_song("search query artist song", mock_member)

    assert song.title == "First Search Result"
    assert song.webpage_url == "https://www.youtube.com/watch?v=search1"

@pytest.mark.asyncio
async def test_extract_song_empty_or_failure_raises_error(mock_member):
    extractor = YouTubeExtractor()
    with patch.object(extractor, "_extract_info_sync", side_effect=Exception("Network error")):
        with pytest.raises(AudioExtractionError) as exc_info:
            await extractor.extract_song("https://bad.url", mock_member)
        assert "Could not retrieve audio" in str(exc_info.value)

def test_create_audio_source():
    extractor = YouTubeExtractor()
    with patch("discord.FFmpegPCMAudio") as mock_ffmpeg, \
         patch("discord.PCMVolumeTransformer") as mock_volume:
        mock_ffmpeg_instance = MagicMock()
        mock_ffmpeg.return_value = mock_ffmpeg_instance

        mock_volume_instance = MagicMock()
        mock_volume.return_value = mock_volume_instance

        source = extractor.create_audio_source("https://stream.url", ffmpeg_path="ffmpeg", volume=0.7)

        mock_ffmpeg.assert_called_once()
        args, kwargs = mock_ffmpeg.call_args
        assert args[0] == "https://stream.url"
        assert kwargs["executable"] == "ffmpeg"
        assert "-reconnect 1" in kwargs["before_options"]
        mock_volume.assert_called_once_with(mock_ffmpeg_instance, volume=0.7)
        assert source == mock_volume_instance
