"""Music cog providing hybrid (slash & prefix) commands for YouTube playback."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
import discord
from discord.ext import commands

from src.config import BotConfig
from src.errors import AudioExtractionError
from src.models.song import RepeatMode, Song
from src.services.player import GuildMusicPlayer
from src.services.ytdl import YouTubeExtractor

if TYPE_CHECKING:
    from discord.ext.commands import Context

logger = logging.getLogger(__name__)

class MusicCog(commands.Cog, name="Music"):
    """Music playback commands: play, pause, resume, skip, stop, queue, repeat, volume, leave."""

    def __init__(self, bot: commands.Bot, config: BotConfig) -> None:
        self.bot = bot
        self.config = config
        self.extractor = YouTubeExtractor()
        self.players: dict[int, GuildMusicPlayer] = {}

    async def send_response(
        self,
        ctx: Context,
        content: str | None = None,
        embed: discord.Embed | None = None,
    ) -> discord.Message | None:
        """Send a response, replacing the deferred thinking message if in a deferred interaction."""
        interaction = getattr(ctx, "interaction", None)
        if interaction is not None:
            if interaction.response.is_done():
                kwargs: dict[str, Any] = {}
                if content is not None:
                    kwargs["content"] = content
                if embed is not None:
                    kwargs["embed"] = embed
                try:
                    return await interaction.edit_original_response(**kwargs)
                except Exception as err:
                    logger.debug("edit_original_response failed, falling back to followup: %s", err)
                    return await interaction.followup.send(content=content, embed=embed)
            else:
                if embed is not None and content is not None:
                    return await ctx.send(content, embed=embed)
                elif embed is not None:
                    return await ctx.send(embed=embed)
                else:
                    return await ctx.send(content)
        else:
            if embed is not None and content is not None:
                return await ctx.send(content, embed=embed)
            elif embed is not None:
                return await ctx.send(embed=embed)
            else:
                return await ctx.send(content)

    def get_player(self, ctx: Context, voice_client: discord.VoiceClient) -> GuildMusicPlayer:
        """Retrieve or instantiate a GuildMusicPlayer for the given guild."""
        guild_id = ctx.guild.id
        if guild_id not in self.players or self.players[guild_id].voice_client != voice_client:
            async def on_track_start(song: Song) -> None:
                player = self.players.get(guild_id)
                channel = player.bound_channel if (player and player.bound_channel) else ctx.channel
                embed = song.create_embed(status="Now Playing")
                try:
                    await channel.send(embed=embed)
                except Exception as err:
                    logger.warning("Failed to send now playing message to channel: %s", err)

            async def on_error(song: Song, error: Exception) -> None:
                player = self.players.get(guild_id)
                channel = player.bound_channel if (player and player.bound_channel) else ctx.channel
                try:
                    await channel.send(f"❌ An error occurred while attempting to play **{song.title}**: {error}")
                except Exception as err:
                    logger.warning("Failed to send playback error message: %s", err)

            async def on_disconnect() -> None:
                player = self.players.get(guild_id)
                channel = player.bound_channel if (player and player.bound_channel) else ctx.channel
                await self.cleanup_player(guild_id)
                try:
                    await channel.send("🔇 Inactive for 3 minutes. Disconnected from voice channel.")
                except Exception:
                    pass

            self.players[guild_id] = GuildMusicPlayer(
                voice_client=voice_client,
                ffmpeg_path=self.config.ffmpeg_path,
                default_volume=self.config.default_volume,
                on_track_start=on_track_start,
                on_disconnect=on_disconnect,
                on_error=on_error,
                bound_channel=ctx.channel,
            )

        player = self.players[guild_id]
        player.bound_channel = ctx.channel
        return player

    async def cleanup_player(self, guild_id: int) -> None:
        """Clean up player resources and disconnect voice client."""
        player = self.players.pop(guild_id, None)
        if player:
            player.destroy()
            if player.voice_client and player.voice_client.is_connected():
                await player.voice_client.disconnect()

    @commands.hybrid_command(name="play", description="Play audio from a YouTube URL or search query.")
    async def play(self, ctx: Context, *, query: str | None = None) -> None:
        """Connects to user's VC and plays or queues YouTube audio."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await self.send_response(ctx, "❌ You must be in a voice channel to use the play command.")
            return

        target_channel = ctx.author.voice.channel

        player = self.players.get(ctx.guild.id)
        if player:
            player.bound_channel = ctx.channel

        # Support play with no query: resume if paused, or show current track
        if not query or not query.strip():
            if player and player.is_paused:
                player.resume()
                await self.send_response(ctx, "▶️ Playback resumed.")
                return
            elif player and (player.is_playing or player.current_song is not None):
                embed = player.current_song.create_embed(status="Currently Playing")
                await self.send_response(ctx, embed=embed)
                return
            else:
                await self.send_response(ctx, "❌ Please provide a song name or YouTube link to play. Example: `!play never gonna give you up`")
                return

        await ctx.defer()

        # Connect or move to voice channel
        voice_client: discord.VoiceClient | None = ctx.guild.voice_client
        if voice_client is None:
            voice_client = await target_channel.connect()
            import asyncio
            await asyncio.sleep(0.5)
        elif voice_client.channel != target_channel:
            await voice_client.move_to(target_channel)

        try:
            song = await self.extractor.extract_song(query.strip(), ctx.author)
        except AudioExtractionError as err:
            await self.send_response(ctx, f"❌ Could not extract audio: {err}")
            return
        except Exception as err:
            logger.error("Unexpected error extracting song '%s': %s", query, err, exc_info=True)
            await self.send_response(ctx, f"❌ An unexpected error occurred while preparing audio: {err}")
            return

        player = self.get_player(ctx, voice_client)
        player.bound_channel = ctx.channel
        is_currently_playing = player.is_playing or player.current_song is not None

        if is_currently_playing:
            await player.enqueue(song)
            embed = song.create_embed(status="Added to Queue")
            await self.send_response(ctx, embed=embed)
        else:
            player.last_announced_url = song.webpage_url
            await player.enqueue(song)
            embed = song.create_embed(status="Now Playing")
            await self.send_response(ctx, embed=embed)

    @commands.hybrid_command(name="pause", description="Pause currently playing music.")
    async def pause(self, ctx: Context) -> None:
        """Pause playback."""
        player = self.players.get(ctx.guild.id)
        if not player or not player.is_playing:
            await self.send_response(ctx, "❌ Nothing is currently playing.")
            return

        player.bound_channel = ctx.channel
        if player.pause():
            await self.send_response(ctx, "⏸️ Playback paused.")
        else:
            await self.send_response(ctx, "❌ Could not pause.")

    @commands.hybrid_command(name="resume", description="Resume paused music.")
    async def resume(self, ctx: Context) -> None:
        """Resume paused playback."""
        player = self.players.get(ctx.guild.id)
        if not player or not player.is_paused:
            await self.send_response(ctx, "❌ Audio is not currently paused.")
            return

        player.bound_channel = ctx.channel
        if player.resume():
            await self.send_response(ctx, "▶️ Playback resumed.")
        else:
            await self.send_response(ctx, "❌ Could not resume.")

    @commands.hybrid_command(name="skip", description="Skip currently playing track.")
    async def skip(self, ctx: Context) -> None:
        """Skip current track."""
        player = self.players.get(ctx.guild.id)
        if not player or (not player.is_playing and not player.is_paused):
            await self.send_response(ctx, "❌ Nothing is currently playing to skip.")
            return

        player.bound_channel = ctx.channel
        player.skip()
        await self.send_response(ctx, "⏭️ Skipped current track.")

    @commands.hybrid_command(name="stop", description="Stop music and clear queue.")
    async def stop(self, ctx: Context) -> None:
        """Stop audio and clear queue."""
        player = self.players.get(ctx.guild.id)
        if not player:
            await self.send_response(ctx, "❌ Bot is not playing music.")
            return

        player.bound_channel = ctx.channel
        player.stop()
        await self.send_response(ctx, "⏹️ Stopped playback and cleared queue.")

    @commands.hybrid_command(
        name="repeat",
        aliases=["loop"],
        description="Toggle or set repeat mode: off, song, or queue."
    )
    async def repeat(self, ctx: Context, mode: str | None = None) -> None:
        """Toggle or set repeating for the current song or entire queue."""
        player = self.players.get(ctx.guild.id)
        if not player:
            await self.send_response(ctx, "❌ Bot is not active in a voice channel.")
            return

        player.bound_channel = ctx.channel
        try:
            new_mode = player.toggle_repeat_mode(mode)
        except ValueError as err:
            await self.send_response(ctx, f"❌ {err}")
            return

        if new_mode == RepeatMode.SONG:
            await self.send_response(ctx, "🔂 Repeat mode set to: **Current Song** (looping this song).")
        elif new_mode == RepeatMode.QUEUE:
            await self.send_response(ctx, "🔁 Repeat mode set to: **Entire Queue** (looping all songs).")
        else:
            await self.send_response(ctx, "➡️ Repeat mode set to: **Off**.")

    @commands.hybrid_command(name="queue", description="Display currently queued songs.")
    async def queue(self, ctx: Context) -> None:
        """List upcoming tracks."""
        player = self.players.get(ctx.guild.id)
        if not player or (player.current_song is None and not player.queue):
            await self.send_response(ctx, "📭 The queue is currently empty.")
            return

        player.bound_channel = ctx.channel
        lines: list[str] = []
        if player.current_song:
            repeat_tag = " [🔂 Loop]" if player.repeat_mode == RepeatMode.SONG else ""
            lines.append(f"**Now Playing:** [{player.current_song.title}]({player.current_song.webpage_url}) (`{player.current_song.formatted_duration}`){repeat_tag}")

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
        embed.set_footer(text=f"Repeat: {player.repeat_mode.value.capitalize()} • Volume: {int(player.volume * 100)}%")
        await self.send_response(ctx, embed=embed)

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show information about the current song.")
    async def nowplaying(self, ctx: Context) -> None:
        """Show current song embed."""
        player = self.players.get(ctx.guild.id)
        if not player or player.current_song is None:
            await self.send_response(ctx, "❌ Nothing is currently playing.")
            return

        player.bound_channel = ctx.channel
        await self.send_response(ctx, embed=player.current_song.create_embed(status="Now Playing"))

    @commands.hybrid_command(name="volume", description="Adjust playback volume (1-150%).")
    async def volume(self, ctx: Context, percent: int) -> None:
        """Adjust volume."""
        if percent < 1 or percent > 150:
            await self.send_response(ctx, "❌ Please provide a volume between 1 and 150.")
            return

        player = self.players.get(ctx.guild.id)
        if not player:
            await self.send_response(ctx, "❌ Bot is not currently active in a voice channel.")
            return

        player.bound_channel = ctx.channel
        player.set_volume(percent / 100.0)
        await self.send_response(ctx, f"🔊 Volume set to {percent}%.")

    @commands.hybrid_command(name="leave", aliases=["dc", "disconnect"], description="Disconnect from voice channel.")
    async def leave(self, ctx: Context) -> None:
        """Leave voice channel."""
        if ctx.guild.voice_client is None:
            await self.send_response(ctx, "❌ Bot is not in a voice channel.")
            return

        await self.cleanup_player(ctx.guild.id)
        await self.send_response(ctx, "👋 Disconnected from voice channel.")

    async def cog_command_error(self, ctx: Context, error: Exception) -> None:
        """Handle errors raised during cog command execution and respond to user."""
        logger.error("Error executing command '%s': %s", ctx.command, error, exc_info=error)
        if isinstance(error, commands.MissingRequiredArgument):
            await self.send_response(ctx, f"❌ Missing argument: `{error.param.name}`. Use `{self.config.prefix}help {ctx.command}` for usage.")
        elif isinstance(error, commands.BadArgument):
            await self.send_response(ctx, f"❌ Invalid argument: {error}")
        else:
            orig_error = getattr(error, "original", error)
            await self.send_response(ctx, f"❌ An error occurred: {orig_error}")


async def setup(bot: commands.Bot) -> None:
    """Extension entry point for loading cog."""
    config: BotConfig = getattr(bot, "bot_config")
    await bot.add_cog(MusicCog(bot, config))
