"""Per-guild playback controller managing song queue, voice transitions, and audio stream state."""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Coroutine
import logging
from typing import Any
import discord

from src.models.song import RepeatMode, Song
from src.services.ytdl import YouTubeExtractor

logger = logging.getLogger(__name__)

class GuildMusicPlayer:
    """Manages audio playback and the track queue for a single Discord guild."""

    def __init__(
        self,
        voice_client: discord.VoiceClient,
        ffmpeg_path: str = "ffmpeg",
        default_volume: float = 0.5,
        on_track_start: Callable[[Song], Coroutine[Any, Any, None]] | None = None,
        on_disconnect: Callable[[], Coroutine[Any, Any, None]] | None = None,
        on_error: Callable[[Song, Exception], Coroutine[Any, Any, None]] | None = None,
        bound_channel: discord.abc.Messageable | None = None,
    ) -> None:
        self.voice_client = voice_client
        self.ffmpeg_path = ffmpeg_path
        self._volume = default_volume
        self.on_track_start = on_track_start
        self.on_disconnect = on_disconnect
        self.on_error = on_error
        self.bound_channel = bound_channel

        self.repeat_mode: RepeatMode = RepeatMode.OFF
        self._skip_requested: bool = False
        self._last_error: Exception | None = None
        self.last_announced_url: str | None = None

        self._queue: deque[Song] = deque()
        self.current_song: Song | None = None
        self._queue_item_added = asyncio.Event()
        self._track_finished = asyncio.Event()
        self._audio_source: discord.PCMVolumeTransformer | None = None
        self._is_stopped = False
        self._player_task: asyncio.Task[None] | None = None
        self._ensure_player_task()

    def _ensure_player_task(self) -> None:
        """Ensure background playback loop is running."""
        if (self._player_task is None or self._player_task.done()) and not self._is_stopped:
            try:
                loop = asyncio.get_running_loop()
                self._player_task = loop.create_task(self._audio_player_loop())
            except RuntimeError:
                self._player_task = None

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

    def toggle_repeat_mode(self, mode: str | None = None) -> RepeatMode:
        """Toggle or explicitly set the repeat mode ('off', 'song', 'queue')."""
        if mode:
            cleaned = mode.lower().strip()
            if cleaned in ("song", "track", "one", "current"):
                self.repeat_mode = RepeatMode.SONG
            elif cleaned in ("queue", "all"):
                self.repeat_mode = RepeatMode.QUEUE
            elif cleaned in ("off", "none", "disable", "stop"):
                self.repeat_mode = RepeatMode.OFF
            else:
                raise ValueError("Invalid repeat mode. Please choose 'off', 'song', or 'queue'.")
        else:
            if self.repeat_mode == RepeatMode.OFF:
                self.repeat_mode = RepeatMode.SONG
            elif self.repeat_mode == RepeatMode.SONG:
                self.repeat_mode = RepeatMode.QUEUE
            else:
                self.repeat_mode = RepeatMode.OFF

        logger.info("Repeat mode updated to: %s", self.repeat_mode.value)
        return self.repeat_mode

    async def enqueue(self, song: Song) -> None:
        """Add a song to the guild queue."""
        self._ensure_player_task()
        self._queue.append(song)
        self._queue_item_added.set()

    def pause(self) -> bool:
        """Pause playback if currently playing."""
        if self.voice_client.is_playing() and not self.voice_client.is_paused():
            self.voice_client.pause()
            logger.info("Paused playback.")
            return True
        return False

    def resume(self) -> bool:
        """Resume playback if currently paused."""
        if self.voice_client.is_paused():
            self.voice_client.resume()
            logger.info("Resumed playback.")
            return True
        return False

    def skip(self) -> bool:
        """Skip the currently playing track."""
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            logger.info("Skipping track: %s", self.current_song.title if self.current_song else "unknown")
            self._skip_requested = True
            self.voice_client.stop()
            self._track_finished.set()
            return True
        return False

    def stop(self) -> None:
        """Stop playback and clear all queued tracks."""
        self._queue.clear()
        self.current_song = None
        self._skip_requested = False
        self.last_announced_url = None
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
        self._track_finished.set()
        logger.info("Stopped playback and cleared queue.")

    def destroy(self) -> None:
        """Clean up tasks and resources."""
        self._is_stopped = True
        self.stop()
        if self._player_task and not self._player_task.done():
            self._player_task.cancel()

    def _play_next_callback(self, error: Exception | None) -> None:
        """Callback invoked by discord.py in AudioPlayer worker thread when audio track completes or errors."""
        self._last_error = error
        if error:
            logger.error("Audio playback error encountered: %s", error, exc_info=error)
        else:
            logger.info("Audio track finished playing successfully.")

        try:
            loop = self.voice_client.loop
            loop.call_soon_threadsafe(self._track_finished.set)
        except Exception:
            self._track_finished.set()

    async def _audio_player_loop(self) -> None:
        """Background loop continuously consuming queued tracks."""
        while not self._is_stopped:
            while not self._queue and not self._is_stopped:
                self.current_song = None
                self._queue_item_added.clear()
                try:
                    await asyncio.wait_for(self._queue_item_added.wait(), timeout=180.0)
                except asyncio.TimeoutError:
                    if self.on_disconnect and not self._is_stopped:
                        await self.on_disconnect()
                    return

            if self._is_stopped:
                break

            # If voice client is still actively playing, wait for it to fully stop before starting next track
            while self.voice_client.is_playing() and not self._is_stopped:
                await asyncio.sleep(0.1)

            if self._is_stopped:
                break

            self.current_song = self._queue.popleft()
            self._track_finished.clear()
            self._last_error = None

            try:
                self._audio_source = YouTubeExtractor.create_audio_source(
                    self.current_song.stream_url,
                    ffmpeg_path=self.ffmpeg_path,
                    volume=self._volume,
                )
                self.voice_client.play(self._audio_source, after=self._play_next_callback)

                if self.on_track_start and self.last_announced_url != self.current_song.webpage_url:
                    self.last_announced_url = self.current_song.webpage_url
                    await self.on_track_start(self.current_song)

            except Exception as err:
                logger.error("Failed to start playback for %s: %s", self.current_song.title, err, exc_info=True)
                self._last_error = err
                self._track_finished.set()

            await self._track_finished.wait()

            # If an error occurred (either at startup or during playback), notify user
            if self._last_error and not self._skip_requested and self.on_error and self.current_song:
                try:
                    await self.on_error(self.current_song, self._last_error)
                except Exception as callback_err:
                    logger.warning("Error running on_error callback: %s", callback_err)

            # Handle repeat mode
            if self._skip_requested:
                self._skip_requested = False
            elif not self._last_error and self.current_song:
                if self.repeat_mode == RepeatMode.SONG:
                    self._queue.appendleft(self.current_song)
                elif self.repeat_mode == RepeatMode.QUEUE:
                    self._queue.append(self.current_song)
