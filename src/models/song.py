"""Song representation dataclass and embed generator."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import discord

class RepeatMode(str, Enum):
    """Repeat modes for guild music playback."""
    OFF = "off"
    SONG = "song"
    QUEUE = "queue"

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
