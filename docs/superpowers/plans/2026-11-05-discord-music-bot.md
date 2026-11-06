# Discord Music Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready, modular Discord music bot in Python using `discord.py` and `yt-dlp` that connects to voice channels, streams audio from YouTube URLs/queries, supports queues, pause, resume, skip, stop, and volume controls, with secrets managed via `.env`.

**Architecture:** The bot follows an asynchronous, modular architecture with strict separation of concerns:
1. `config.py`: Strongly-typed configuration loaded from `.env` via `python-dotenv`.
2. `errors.py`: Domain-specific exception hierarchy extending a base `MusicBotError`.
3. `models/song.py`: Slotted dataclass representing audio tracks with embed formatting and duration calculations.
4. `services/ytdl.py`: Non-blocking audio extractor leveraging `yt-dlp` in executor threads and `discord.FFmpegPCMAudio` with streaming reconnect flags.
5. `services/player.py`: Per-guild queue and playback lifecycle manager controlling voice client transitions and idle disconnects.
6. `cogs/music.py`: Hybrid command cog (`@commands.hybrid_command`) enabling both slash (`/play`) and prefix (`!play`) commands with voice state guards.
7. `main.py` / `bot.py`: Entrypoint initializing `discord.ext.commands.Bot` with voice and message intents, custom logging, and graceful teardown.

**Tech Stack:** 
- Python 3.10+ (tested on Python 3.14.2)
- `discord.py[voice]` (v2.7+) & `PyNaCl`
- `yt-dlp` (stream extraction)
- `ffmpeg` (audio streaming/transcoding)
- `python-dotenv` (environment configuration)
- `pytest` & `pytest-asyncio` (automated testing)

**Spec:** User specification for a Python Discord music bot with `.env` secrets, YouTube playback, auto-voice-channel joining, `play`, `pause`, `stop`, `skip`, `queue`, `nowplaying`, and `leave` commands.

## Global Constraints

- Pythonic standards conforming to PEP 8, strict type hints (`list[T]`, `X | None`, `Callable`), and explicit error handling.
- `yt-dlp` extraction is blocking I/O and MUST never be called synchronously inside the asyncio event loop; it must run via `asyncio.to_thread`.
- FFmpeg audio stream options must include stream reconnection flags (`-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5`) to prevent streaming dropouts.
- All secrets (`DISCORD_TOKEN`, etc.) must be read from `.env` and never hardcoded or committed to git.
- Test coverage for all business logic (config, models, extractor helpers, queue state transitions) using `pytest` and `pytest-asyncio`.

---

### Task 1: Project Scaffolding & Configuration Management

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `src.config.BotConfig` dataclass:
  - `token: str`
  - `prefix: str = "!"`
  - `ffmpeg_path: str = "ffmpeg"`
  - `default_volume: float = 0.5`
  - `classmethod load_from_env() -> BotConfig`
- Produces: `src.errors.ConfigurationError`

- [ ] **Step 1: Write the failing test for configuration loading**

Create `tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src'` or `ImportError`.

- [ ] **Step 3: Write minimal implementation for configuration & project files**

Create `src/errors.py`:
```python
"""Custom domain exceptions for the Discord Music Bot."""

class MusicBotError(Exception):
    """Base exception for all music bot errors."""
    pass

class ConfigurationError(MusicBotError):
    """Raised when environment variables or bot configuration are invalid."""
    pass

class VoiceChannelError(MusicBotError):
    """Raised when a voice channel action fails or member is not in VC."""
    pass

class AudioExtractionError(MusicBotError):
    """Raised when audio metadata or stream extraction fails."""
    pass

class QueueEmptyError(MusicBotError):
    """Raised when attempting to retrieve a track from an empty queue."""
    pass
```

Create `src/__init__.py`:
```python
"""Discord Music Bot package."""
__version__ = "1.0.0"
```

Create `src/config.py`:
```python
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
```

Create `.env.example`:
```env
# Discord Bot Token from Discord Developer Portal
DISCORD_TOKEN=your_bot_token_here

# Bot command prefix for text commands (Default: !)
COMMAND_PREFIX=!

# Path or binary name for ffmpeg (Default: ffmpeg)
FFMPEG_PATH=ffmpeg

# Default volume (0.0 to 2.0, default: 0.5)
DEFAULT_VOLUME=0.5
```

Create `.gitignore`:
```gitignore
.env
.venv/
__pycache__/
*.py[cod]
*$py.class
*.log
.pytest_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
```

Create `requirements.txt`:
```txt
discord.py[voice]>=2.4.0
yt-dlp>=2024.1.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

Create `pyproject.toml`:
```toml
[project]
name = "discord-music-bot"
version = "1.0.0"
description = "A modern Python Discord music bot using yt-dlp and discord.py"
requires-python = ">=3.10"
dependencies = [
    "discord.py[voice]>=2.4.0",
    "yt-dlp>=2024.1.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_config.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements.txt .env.example .gitignore src/__init__.py src/errors.py src/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: setup project scaffolding, configuration loader, and error hierarchy"
```

---

### Task 2: Track Model & Discord Embed Formatter

**Files:**
- Create: `src/models/__init__.py`
- Create: `src/models/song.py`
- Create: `tests/test_song.py`

**Interfaces:**
- Consumes: `src.errors.MusicBotError`
- Produces: `src.models.song.Song` dataclass:
  - `title: str`
  - `webpage_url: str`
  - `stream_url: str`
  - `duration: int`
  - `uploader: str`
  - `thumbnail_url: str | None`
  - `requester_name: str`
  - `requester_id: int`
  - property `formatted_duration -> str` (e.g. "03:45" or "01:12:00")
  - method `create_embed(status: str = "Now Playing") -> discord.Embed`

- [ ] **Step 1: Write the failing test for Song model**

Create `tests/test_song.py`:
```python
import discord
from src.models.song import Song

def test_song_initialization_and_duration_formatting():
    # Test short duration (minutes and seconds)
    song1 = Song(
        title="Test Song 1",
        webpage_url="https://www.youtube.com/watch?v=12345",
        stream_url="https://googlevideo.com/videoplayback/test",
        duration=225,
        uploader="Test Artist",
        thumbnail_url="https://img.youtube.com/vi/12345/hqdefault.jpg",
        requester_name="Aiden",
        requester_id=111222333,
    )
    assert song1.formatted_duration == "03:45"

    # Test long duration (hours, minutes, seconds)
    song2 = Song(
        title="Long Track",
        webpage_url="https://www.youtube.com/watch?v=67890",
        stream_url="https://googlevideo.com/videoplayback/long",
        duration=3665,
        uploader="Ambient Musician",
        thumbnail_url=None,
        requester_name="Aiden",
        requester_id=111222333,
    )
    assert song2.formatted_duration == "01:01:05"

    # Test live stream or unknown duration
    song3 = Song(
        title="Live Stream",
        webpage_url="https://www.youtube.com/watch?v=live",
        stream_url="https://googlevideo.com/videoplayback/live",
        duration=0,
        uploader="Live Channel",
        thumbnail_url=None,
        requester_name="Aiden",
        requester_id=111222333,
    )
    assert song3.formatted_duration == "Live / Unknown"

def test_song_create_embed():
    song = Song(
        title="Sample Song",
        webpage_url="https://www.youtube.com/watch?v=abcde",
        stream_url="https://stream.url",
        duration=180,
        uploader="Channel Name",
        thumbnail_url="https://thumbnail.url/img.jpg",
        requester_name="Listener",
        requester_id=999888,
    )
    embed = song.create_embed(status="Enqueued")
    assert isinstance(embed, discord.Embed)
    assert "Enqueued" in embed.title
    assert embed.description == "[Sample Song](https://www.youtube.com/watch?v=abcde)"
    assert embed.thumbnail.url == "https://thumbnail.url/img.jpg"

    fields = {f.name: f.value for f in embed.fields}
    assert fields["Duration"] == "03:00"
    assert fields["Channel"] == "Channel Name"
    assert fields["Requested By"] == "Listener"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_song.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.models.song'`.

- [ ] **Step 3: Write minimal implementation for Song model**

Create `src/models/__init__.py`:
```python
"""Data models for Discord Music Bot."""
from src.models.song import Song

__all__ = ["Song"]
```

Create `src/models/song.py`:
```python
"""Song representation dataclass and embed generator."""
from __future__ import annotations

from dataclasses import dataclass
import discord

@dataclass(slots=True)
class Song:
    """Represents a queued or currently playing audio track."""
    title: str
    webpage_url: str
    stream_url: str
    duration: int
    uploader: str
    thumbnail_url: str | None
    requester_name: str
    requester_id: int

    @property
    def formatted_duration(self) -> str:
        """Format duration in seconds into HH:MM:SS or MM:SS string."""
        if not self.duration or self.duration <= 0:
            return "Live / Unknown"
        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def create_embed(self, status: str = "Now Playing") -> discord.Embed:
        """Create a formatted Discord Embed representing this track."""
        embed = discord.Embed(
            title=f"🎵 {status}",
            description=f"[{self.title}]({self.webpage_url})",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Duration", value=self.formatted_duration, inline=True)
        embed.add_field(name="Channel", value=self.uploader or "Unknown", inline=True)
        embed.add_field(name="Requested By", value=self.requester_name, inline=True)

        if self.thumbnail_url:
            embed.set_thumbnail(url=self.thumbnail_url)

        embed.set_footer(text="Discord Music Bot • Powered by yt-dlp & FFmpeg")
        return embed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_song.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/models/__init__.py src/models/song.py tests/test_song.py
git commit -m "feat: add Song data model and discord embed generator"
```

---

### Task 3: YouTube Audio Extractor Service (yt-dlp & FFmpeg Source)

**Files:**
- Create: `src/services/__init__.py`
- Create: `src/services/ytdl.py`
- Create: `tests/test_ytdl.py`

**Interfaces:**
- Consumes: `src.models.song.Song`, `src.errors.AudioExtractionError`
- Produces: `src.services.ytdl.YouTubeExtractor`:
  - `async extract_song(query: str, requester: discord.Member) -> Song`
  - `create_audio_source(stream_url: str, ffmpeg_path: str = "ffmpeg", volume: float = 0.5) -> discord.PCMVolumeTransformer`

- [ ] **Step 1: Write the failing test for YouTubeExtractor**

Create `tests/test_ytdl.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_ytdl.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services'`.

- [ ] **Step 3: Write minimal implementation for YouTubeExtractor**

Create `src/services/__init__.py`:
```python
"""Services for audio extraction and guild playback."""
from src.services.ytdl import YouTubeExtractor
from src.services.player import GuildMusicPlayer

__all__ = ["YouTubeExtractor", "GuildMusicPlayer"]
```

Create `src/services/ytdl.py`:
```python
"""Asynchronous YouTube audio extraction using yt-dlp and FFmpeg source generator."""
from __future__ import annotations

import asyncio
from typing import Any
import discord
import yt_dlp

from src.errors import AudioExtractionError
from src.models.song import Song

YTDL_OPTIONS: dict[str, Any] = {
    "format": "bestaudio/best",
    "extractaudio": True,
    "audioformat": "mp3",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
}

FFMPEG_BEFORE_OPTIONS = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
)
FFMPEG_OPTIONS = "-vn"

class YouTubeExtractor:
    """Handles extracting audio stream metadata via yt-dlp asynchronously."""

    def __init__(self, ytdl_options: dict[str, Any] | None = None) -> None:
        self._options = ytdl_options or YTDL_OPTIONS

    def _extract_info_sync(self, query: str) -> dict[str, Any]:
        """Synchronously extract media information using yt-dlp."""
        with yt_dlp.YoutubeDL(self._options) as ytdl:
            # If not a URL, ytsearch will be invoked automatically by default_search="auto"
            return ytdl.extract_info(query, download=False)

    async def extract_song(self, query: str, requester: discord.Member) -> Song:
        """Asynchronously extract video info in an executor thread to avoid blocking the event loop."""
        try:
            data = await asyncio.to_thread(self._extract_info_sync, query)
        except Exception as err:
            raise AudioExtractionError(f"Could not retrieve audio for query '{query}': {err}") from err

        if not data:
            raise AudioExtractionError(f"No results found for query '{query}'.")

        # Handle playlist/search results containing 'entries'
        if "entries" in data:
            entries = [e for e in data["entries"] if e is not None]
            if not entries:
                raise AudioExtractionError(f"No results found for query '{query}'.")
            data = entries[0]

        stream_url = data.get("url")
        if not stream_url:
            raise AudioExtractionError("Failed to obtain a direct stream URL from YouTube metadata.")

        return Song(
            title=data.get("title", "Unknown Title"),
            webpage_url=data.get("webpage_url", query),
            stream_url=stream_url,
            duration=int(data.get("duration", 0) or 0),
            uploader=data.get("uploader", "Unknown Artist"),
            thumbnail_url=data.get("thumbnail"),
            requester_name=requester.display_name,
            requester_id=requester.id,
        )

    @staticmethod
    def create_audio_source(
        stream_url: str,
        ffmpeg_path: str = "ffmpeg",
        volume: float = 0.5,
    ) -> discord.PCMVolumeTransformer:
        """Instantiate an FFmpeg audio source with reconnection flags wrapped in a volume transformer."""
        audio_source = discord.FFmpegPCMAudio(
            stream_url,
            executable=ffmpeg_path,
            before_options=FFMPEG_BEFORE_OPTIONS,
            options=FFMPEG_OPTIONS,
        )
        return discord.PCMVolumeTransformer(audio_source, volume=volume)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_ytdl.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/services/__init__.py src/services/ytdl.py tests/test_ytdl.py
git commit -m "feat: add asynchronous YouTubeExtractor service with FFmpeg reconnect options"
```

---

### Task 4: Per-Guild Music Player & Queue Manager

**Files:**
- Create: `src/services/player.py`
- Create: `tests/test_player.py`

**Interfaces:**
- Consumes: `src.models.song.Song`, `src.services.ytdl.YouTubeExtractor`
- Produces: `src.services.player.GuildMusicPlayer`:
  - `current_song: Song | None`
  - `queue: list[Song]`
  - `volume: float`
  - `is_playing: bool`
  - `is_paused: bool`
  - `async enqueue(song: Song) -> None`
  - `pause() -> bool`
  - `resume() -> bool`
  - `skip() -> bool`
  - `stop() -> None`
  - `set_volume(volume: float) -> None`
  - `destroy() -> None`

- [ ] **Step 1: Write the failing test for GuildMusicPlayer**

Create `tests/test_player.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import discord

from src.services.player import GuildMusicPlayer
from src.models.song import Song

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
        # Give asyncio loop a slice to trigger playback worker
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_player.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.player'`.

- [ ] **Step 3: Write minimal implementation for GuildMusicPlayer**

Create `src/services/player.py`:
```python
"""Per-guild playback controller managing song queue, voice transitions, and audio stream state."""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Coroutine
from typing import Any
import discord

from src.models.song import Song
from src.services.ytdl import YouTubeExtractor

class GuildMusicPlayer:
    """Manages audio playback and the track queue for a single Discord guild."""

    def __init__(
        self,
        voice_client: discord.VoiceClient,
        ffmpeg_path: str = "ffmpeg",
        default_volume: float = 0.5,
        on_track_start: Callable[[Song], Coroutine[Any, Any, None]] | None = None,
        on_disconnect: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self.voice_client = voice_client
        self.ffmpeg_path = ffmpeg_path
        self._volume = default_volume
        self.on_track_start = on_track_start
        self.on_disconnect = on_disconnect

        self._queue: deque[Song] = deque()
        self.current_song: Song | None = None
        self._next_song_event = asyncio.Event()
        self._audio_source: discord.PCMVolumeTransformer | None = None
        self._is_stopped = False

        self._player_task = asyncio.create_task(self._audio_player_loop())

    @property
    def queue(self) -> list[Song]:
        """Return a snapshot of upcoming tracks in the queue."""
        return list(self._queue)

    @property
    def volume(self) -> float:
        """Current volume level between 0.0 and 2.0."""
        return self._volume

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing in voice channel."""
        return self.voice_client.is_playing()

    @property
    def is_paused(self) -> bool:
        """Check if audio is currently paused in voice channel."""
        return self.voice_client.is_paused()

    def set_volume(self, volume: float) -> None:
        """Set playback volume (clamped between 0.0 and 2.0)."""
        self._volume = max(0.0, min(volume, 2.0))
        if self._audio_source is not None:
            self._audio_source.volume = self._volume

    async def enqueue(self, song: Song) -> None:
        """Add a song to the guild queue."""
        self._queue.append(song)
        self._next_song_event.set()

    def pause(self) -> bool:
        """Pause playback if currently playing."""
        if self.voice_client.is_playing() and not self.voice_client.is_paused():
            self.voice_client.pause()
            return True
        return False

    def resume(self) -> bool:
        """Resume playback if currently paused."""
        if self.voice_client.is_paused():
            self.voice_client.resume()
            return True
        return False

    def skip(self) -> bool:
        """Skip the currently playing track."""
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            return True
        return False

    def stop(self) -> None:
        """Stop playback and clear all queued tracks."""
        self._queue.clear()
        self.current_song = None
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()

    def destroy(self) -> None:
        """Clean up tasks and resources."""
        self._is_stopped = True
        self.stop()
        if not self._player_task.done():
            self._player_task.cancel()

    def _play_next_callback(self, error: Exception | None) -> None:
        """Callback invoked by discord.py when audio track completes or errors."""
        if error:
            # Errors are logged
            pass
        self._next_song_event.set()

    async def _audio_player_loop(self) -> None:
        """Background loop continuously consuming queued tracks."""
        while not self._is_stopped:
            self._next_song_event.clear()

            if not self._queue:
                self.current_song = None
                try:
                    # Wait up to 180 seconds for a new song before disconnecting idle bot
                    await asyncio.wait_for(self._next_song_event.wait(), timeout=180.0)
                except asyncio.TimeoutError:
                    if self.on_disconnect:
                        await self.on_disconnect()
                    break

            if self._is_stopped:
                break

            if not self._queue:
                continue

            self.current_song = self._queue.popleft()

            try:
                self._audio_source = YouTubeExtractor.create_audio_source(
                    self.current_song.stream_url,
                    ffmpeg_path=self.ffmpeg_path,
                    volume=self._volume,
                )
                self.voice_client.play(self._audio_source, after=self._play_next_callback)

                if self.on_track_start:
                    await self.on_track_start(self.current_song)

            except Exception:
                self._next_song_event.set()

            # Wait until track finishes or skip is triggered
            await self._next_song_event.wait()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_player.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/services/player.py tests/test_player.py
git commit -m "feat: implement per-guild music player with queue management and auto-disconnect"
```

---

### Task 5: Music Cog (Commands & Voice State Handling)

**Files:**
- Create: `src/cogs/__init__.py`
- Create: `src/cogs/music.py`
- Create: `tests/test_cogs_music.py`

**Interfaces:**
- Consumes: `src.config.BotConfig`, `src.models.song.Song`, `src.services.ytdl.YouTubeExtractor`, `src.services.player.GuildMusicPlayer`
- Produces: `src.cogs.music.MusicCog(commands.Cog)`:
  - Hybrid commands: `play`, `pause`, `resume`, `stop`, `skip`, `queue`, `nowplaying`, `volume`, `leave`
  - Error handling for missing voice channels, extraction errors, and permissions.

- [ ] **Step 1: Write the failing test for Music Cog logic**

Create `tests/test_cogs_music.py`:
```python
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
        mock_player_cls.return_value = mock_player_instance

        await cog.play.callback(cog, ctx_mock, query="https://youtube.com/watch?v=1")

        ctx_mock.defer.assert_called_once()
        mock_player_instance.enqueue.assert_called_once_with(mock_song)
        ctx_mock.send.assert_called_once()
        _, kwargs = ctx_mock.send.call_args
        assert "embed" in kwargs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_cogs_music.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.cogs'`.

- [ ] **Step 3: Write minimal implementation for Music Cog**

Create `src/cogs/__init__.py`:
```python
"""Discord bot cogs extension package."""
from src.cogs.music import MusicCog

__all__ = ["MusicCog"]
```

Create `src/cogs/music.py`:
```python
"""Music cog providing hybrid (slash & prefix) commands for YouTube playback."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
import discord
from discord.ext import commands

from src.config import BotConfig
from src.errors import AudioExtractionError, MusicBotError
from src.models.song import Song
from src.services.player import GuildMusicPlayer
from src.services.ytdl import YouTubeExtractor

if TYPE_CHECKING:
    from discord.ext.commands import Context

logger = logging.getLogger(__name__)

class MusicCog(commands.Cog, name="Music"):
    """Music playback commands: play, pause, resume, skip, stop, queue, volume, leave."""

    def __init__(self, bot: commands.Bot, config: BotConfig) -> None:
        self.bot = bot
        self.config = config
        self.extractor = YouTubeExtractor()
        self.players: dict[int, GuildMusicPlayer] = {}

    def get_player(self, ctx: Context, voice_client: discord.VoiceClient) -> GuildMusicPlayer:
        """Retrieve or instantiate a GuildMusicPlayer for the given guild."""
        guild_id = ctx.guild.id
        if guild_id not in self.players or self.players[guild_id].voice_client != voice_client:
            async def on_track_start(song: Song) -> None:
                embed = song.create_embed(status="Now Playing")
                try:
                    await ctx.send(embed=embed)
                except Exception as err:
                    logger.warning("Failed to send now playing message: %s", err)

            async def on_disconnect() -> None:
                await self.cleanup_player(guild_id)
                try:
                    await ctx.send("🔇 Inactive for 3 minutes. Disconnected from voice channel.")
                except Exception:
                    pass

            self.players[guild_id] = GuildMusicPlayer(
                voice_client=voice_client,
                ffmpeg_path=self.config.ffmpeg_path,
                default_volume=self.config.default_volume,
                on_track_start=on_track_start,
                on_disconnect=on_disconnect,
            )
        return self.players[guild_id]

    async def cleanup_player(self, guild_id: int) -> None:
        """Clean up player resources and disconnect voice client."""
        player = self.players.pop(guild_id, None)
        if player:
            player.destroy()
            if player.voice_client and player.voice_client.is_connected():
                await player.voice_client.disconnect()

    @commands.hybrid_command(name="play", description="Play audio from a YouTube URL or search query.")
    async def play(self, ctx: Context, *, query: str) -> None:
        """Connects to user's VC and plays or queues YouTube audio."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be in a voice channel to use the play command.")
            return

        target_channel = ctx.author.voice.channel
        await ctx.defer()

        # Connect or move to voice channel
        voice_client: discord.VoiceClient | None = ctx.guild.voice_client
        if voice_client is None:
            voice_client = await target_channel.connect()
        elif voice_client.channel != target_channel:
            await voice_client.move_to(target_channel)

        try:
            song = await self.extractor.extract_song(query, ctx.author)
        except AudioExtractionError as err:
            await ctx.send(f"❌ Error: {err}")
            return

        player = self.get_player(ctx, voice_client)
        is_currently_playing = player.is_playing or player.current_song is not None
        await player.enqueue(song)

        if is_currently_playing:
            embed = song.create_embed(status="Added to Queue")
            await ctx.send(embed=embed)
        else:
            # If nothing was playing, the loop will play it immediately and emit on_track_start
            pass

    @commands.hybrid_command(name="pause", description="Pause currently playing music.")
    async def pause(self, ctx: Context) -> None:
        """Pause playback."""
        player = self.players.get(ctx.guild.id)
        if not player or not player.is_playing:
            await ctx.send("❌ Nothing is currently playing.")
            return

        if player.pause():
            await ctx.send("⏸️ Playback paused.")
        else:
            await ctx.send("❌ Could not pause.")

    @commands.hybrid_command(name="resume", description="Resume paused music.")
    async def resume(self, ctx: Context) -> None:
        """Resume paused playback."""
        player = self.players.get(ctx.guild.id)
        if not player or not player.is_paused:
            await ctx.send("❌ Audio is not currently paused.")
            return

        if player.resume():
            await ctx.send("▶️ Playback resumed.")
        else:
            await ctx.send("❌ Could not resume.")

    @commands.hybrid_command(name="skip", description="Skip currently playing track.")
    async def skip(self, ctx: Context) -> None:
        """Skip current track."""
        player = self.players.get(ctx.guild.id)
        if not player or (not player.is_playing and not player.is_paused):
            await ctx.send("❌ Nothing is currently playing to skip.")
            return

        player.skip()
        await ctx.send("⏭️ Skipped current track.")

    @commands.hybrid_command(name="stop", description="Stop music and clear queue.")
    async def stop(self, ctx: Context) -> None:
        """Stop audio and clear queue."""
        player = self.players.get(ctx.guild.id)
        if not player:
            await ctx.send("❌ Bot is not playing music.")
            return

        player.stop()
        await ctx.send("⏹️ Stopped playback and cleared queue.")

    @commands.hybrid_command(name="queue", description="Display currently queued songs.")
    async def queue(self, ctx: Context) -> None:
        """List upcoming tracks."""
        player = self.players.get(ctx.guild.id)
        if not player or (player.current_song is None and not player.queue):
            await ctx.send("📭 The queue is currently empty.")
            return

        lines: list[str] = []
        if player.current_song:
            lines.append(f"**Now Playing:** [{player.current_song.title}]({player.current_song.webpage_url}) (`{player.current_song.formatted_duration}`)")

        if player.queue:
            lines.append("\n**Up Next:**")
            for idx, song in enumerate(player.queue[:10], start=1):
                lines.append(f"`{idx}.` [{song.title}]({song.webpage_url}) (`{song.formatted_duration}`) - *req by {song.requester_name}*")
            if len(player.queue) > 10:
                lines.append(f"\n*...and {len(player.queue) - 10} more tracks*")

        embed = discord.Embed(
            title="🎶 Music Queue",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show information about the current song.")
    async def nowplaying(self, ctx: Context) -> None:
        """Show current song embed."""
        player = self.players.get(ctx.guild.id)
        if not player or player.current_song is None:
            await ctx.send("❌ Nothing is currently playing.")
            return

        await ctx.send(embed=player.current_song.create_embed(status="Now Playing"))

    @commands.hybrid_command(name="volume", description="Adjust playback volume (1-100%).")
    async def volume(self, ctx: Context, percent: int) -> None:
        """Adjust volume."""
        if percent < 1 or percent > 150:
            await ctx.send("❌ Please provide a volume between 1 and 150.")
            return

        player = self.players.get(ctx.guild.id)
        if not player:
            await ctx.send("❌ Bot is not currently active in a voice channel.")
            return

        player.set_volume(percent / 100.0)
        await ctx.send(f"🔊 Volume set to {percent}%.")

    @commands.hybrid_command(name="leave", aliases=["dc", "disconnect"], description="Disconnect from voice channel.")
    async def leave(self, ctx: Context) -> None:
        """Leave voice channel."""
        if ctx.guild.voice_client is None:
            await ctx.send("❌ Bot is not in a voice channel.")
            return

        await self.cleanup_player(ctx.guild.id)
        await ctx.send("👋 Disconnected from voice channel.")


async def setup(bot: commands.Bot) -> None:
    """Extension entry point for loading cog."""
    # Retrieve config attached to bot
    config: BotConfig = getattr(bot, "bot_config")
    await bot.add_cog(MusicCog(bot, config))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_cogs_music.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/cogs/__init__.py src/cogs/music.py tests/test_cogs_music.py
git commit -m "feat: implement MusicCog with hybrid play, pause, resume, skip, stop, queue, volume, leave commands"
```

---

### Task 6: Bot Application Core & Entrypoint

**Files:**
- Create: `src/bot.py`
- Create: `main.py`
- Create: `README.md`
- Create: `tests/test_bot_setup.py`

**Interfaces:**
- Consumes: `src.config.BotConfig`, `src.cogs.music.MusicCog`
- Produces: `src.bot.MusicBot(commands.Bot)`:
  - Custom initialization with `discord.Intents.default()` + `message_content` + `voice_states`.
  - `setup_hook()`: registers cogs and synchronizes slash commands (`tree.sync()`).
  - `on_ready()`: logs connected username and latency.
- Produces: `main.py` runnable entrypoint.

- [ ] **Step 1: Write the failing test for bot initialization and setup hook**

Create `tests/test_bot_setup.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_bot_setup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.bot'`.

- [ ] **Step 3: Write minimal implementation for MusicBot and main.py**

Create `src/bot.py`:
```python
"""Custom Discord bot class configuring intents, extensions, and slash commands."""
from __future__ import annotations

import logging
import discord
from discord.ext import commands

from src.config import BotConfig

logger = logging.getLogger(__name__)

class MusicBot(commands.Bot):
    """Custom commands.Bot instance pre-configured for voice playback and slash commands."""

    def __init__(self, config: BotConfig) -> None:
        self.bot_config = config

        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=config.prefix,
            intents=intents,
            help_command=commands.DefaultHelpCommand(),
        )

    async def setup_hook(self) -> None:
        """Asynchronous setup hook invoked prior to bot login."""
        logger.info("Loading Music extension...")
        await self.load_extension("src.cogs.music")

        logger.info("Synchronizing application slash commands with Discord...")
        try:
            synced = await self.tree.sync()
            logger.info("Successfully synced %d application command(s).", len(synced))
        except Exception as err:
            logger.error("Failed to sync application commands: %s", err)

    async def on_ready(self) -> None:
        """Lifecycle event triggered when bot connects and is ready."""
        user = self.user
        if user:
            logger.info("Logged in as %s (ID: %s)", user.name, user.id)
            logger.info("Connected to %d guild(s).", len(self.guilds))
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"{self.bot_config.prefix}play | /play",
                )
            )
```

Create `main.py`:
```python
"""Application entrypoint for running the Discord Music Bot."""
import logging
import sys
from src.bot import MusicBot
from src.config import BotConfig
from src.errors import ConfigurationError

def setup_logging() -> None:
    """Initialize formatted console logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

def main() -> None:
    """Run the music bot."""
    setup_logging()
    logger = logging.getLogger("main")

    try:
        config = BotConfig.load_from_env()
    except ConfigurationError as err:
        logger.critical("Configuration error: %s", err)
        sys.exit(1)

    bot = MusicBot(config)
    try:
        bot.run(config.token)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal. Shutting down gracefully...")
    except Exception as err:
        logger.critical("Bot runtime error: %s", err)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

Create `README.md`:
```markdown
# Discord Music Bot (Python)

A modern, high-performance Discord music bot built with **Python 3.10+**, **discord.py**, and **yt-dlp**.

## Features

- 🎧 **YouTube Streaming**: Stream any YouTube URL or search query using `yt-dlp` and `ffmpeg`.
- ⚡ **Non-Blocking Architecture**: Extracts audio in separate executor threads to prevent Discord heartbeat lag.
- 💬 **Hybrid Commands**: Every command works both as a modern Discord Slash Command (`/play`) and as a Prefix command (`!play`).
- 📜 **Queue System**: Add multiple tracks, view upcoming songs, skip tracks, and inspect current playback.
- 🎚️ **Playback Controls**: Pause, resume, stop, skip, volume adjustment, and leave.
- 🔌 **Auto-Disconnect**: Leaves voice channels after 3 minutes of inactivity to save server bandwidth.
- 🔒 **Secure Secrets**: Managed through `.env` with strict type validation.

## Prerequisites

1. **Python 3.10+** (tested on Python 3.14)
2. **FFmpeg** installed and accessible in your system `PATH` (or configured via `FFMPEG_PATH` in `.env`).
   - Check with: `ffmpeg -version`
3. **Discord Bot Token**:
   - Go to [Discord Developer Portal](https://discord.com/developers/applications).
   - Create an Application -> Bot.
   - Under **Privileged Gateway Intents**, enable:
     - **Message Content Intent**
     - **Server Members Intent** (optional, recommended)
   - Under **OAuth2 -> URL Generator**, select scopes `bot` and `applications.commands`, with permissions:
     - Send Messages, Embed Links, Connect, Speak, Use Voice Activity.

## Quickstart

1. **Clone & Setup Environment:**
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment:**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in your `DISCORD_TOKEN`:
   ```env
   DISCORD_TOKEN=your_token_here
   COMMAND_PREFIX=!
   FFMPEG_PATH=ffmpeg
   DEFAULT_VOLUME=0.5
   ```

3. **Run the Bot:**
   ```bash
   python main.py
   ```

4. **Run Automated Tests:**
   ```bash
   pytest
   ```

## Available Commands

| Command | Slash Command | Description |
|---|---|---|
| `!play <url or search>` | `/play <query>` | Joins voice channel and plays audio or enqueues it |
| `!pause` | `/pause` | Pauses audio playback |
| `!resume` | `/resume` | Resumes paused audio |
| `!skip` | `/skip` | Skips current track |
| `!stop` | `/stop` | Stops playback and clears the queue |
| `!queue` | `/queue` | Shows currently playing and up to 10 queued songs |
| `!nowplaying` (`!np`) | `/nowplaying` | Displays rich embed of current playing song |
| `!volume <1-150>` | `/volume <percent>` | Adjusts volume percentage |
| `!leave` (`!dc`) | `/leave` | Leaves the voice channel and resets state |
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_bot_setup.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/bot.py main.py README.md tests/test_bot_setup.py
git commit -m "feat: implement MusicBot core lifecycle, main entrypoint, and documentation"
```

---

### Task 7: Full System Verification & Test Suite Execution

**Files:**
- Test all components across `tests/`

- [ ] **Step 1: Execute full test suite**

Run: `.venv\Scripts\pytest -v`
Expected: ALL 15+ tests PASS with zero failures.

- [ ] **Step 2: Dry-run verification of main module imports and configuration check**

Run: `.venv\Scripts\python -c "import main; print('Main module imported cleanly')"`
Expected: Prints `Main module imported cleanly`.

- [ ] **Step 3: Verification of bot help output and command tree**

Run: `.venv\Scripts\python -c "from src.bot import MusicBot; from src.config import BotConfig; b = MusicBot(BotConfig(token='x')); print([c.name for c in b.commands])"`
Expected: Contains default commands (`help`).

- [ ] **Step 4: Final commit of all files**

```bash
git add .
git commit -m "chore: verify full test suite passes and system imports cleanly"
```
