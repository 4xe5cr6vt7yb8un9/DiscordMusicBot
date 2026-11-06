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
