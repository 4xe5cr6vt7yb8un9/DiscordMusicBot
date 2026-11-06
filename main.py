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
