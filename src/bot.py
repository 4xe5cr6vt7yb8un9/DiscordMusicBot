"""Custom Discord bot class configuring intents, extensions, and slash commands."""
from __future__ import annotations

import logging
import discord
from discord.ext import commands

from src.config import BotConfig

logger = logging.getLogger(__name__)

class MusicBot(commands.Bot):
    """Custom commands.Bot instance pre-configured for voice playback and slash commands."""

    def __init__(self, config: BotConfig, application_id: int | None = None) -> None:
        self.bot_config = config

        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=config.prefix,
            intents=intents,
            help_command=commands.DefaultHelpCommand(),
            application_id=application_id,
        )

    async def setup_hook(self) -> None:
        """Asynchronous setup hook invoked prior to bot login."""
        logger.info("Loading Music extension...")
        await self.load_extension("src.cogs.music")

        # Synchronize slash commands if application_id is established
        if self.application_id:
            try:
                synced = await self.tree.sync()
                logger.info("Successfully synced %d application command(s).", len(synced))
            except Exception as err:
                logger.error("Failed to sync application commands: %s", err)
        else:
            logger.debug("Application ID not yet available; slash commands will sync upon login.")

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
