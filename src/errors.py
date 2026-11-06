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
