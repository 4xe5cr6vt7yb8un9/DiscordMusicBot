"""Music cog providing hybrid (slash & prefix) commands for YouTube playback."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
import discord
from discord.ext import commands

from src.config import BotConfig
from src.errors import AudioExtractionError
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
            # Allow voice gateway and encryption handshake to settle
            import asyncio
            await asyncio.sleep(0.5)
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

    @commands.hybrid_command(name="volume", description="Adjust playback volume (1-150%).")
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
    config: BotConfig = getattr(bot, "bot_config")
    await bot.add_cog(MusicCog(bot, config))
