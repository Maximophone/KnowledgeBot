"""
Notification utilities for Obsidian AI processing.
Provides sound notifications for various events in the system.
"""
import platform
import logging
import os
from typing import Optional, Union
from config import user_config
from config.paths import PATHS

logger = logging.getLogger(__name__)

# Sound notification settings - use values from user_config
ENABLE_SOUND_NOTIFICATION = getattr(user_config, 'ENABLE_AI_COMPLETION_SOUND', True)
NOTIFICATION_SOUND = getattr(user_config, 'AI_COMPLETION_SOUND', 'SystemAsterisk')

# Import winsound only on Windows
_winsound_available = False
if platform.system() == "Windows":
    try:
        import winsound
        _winsound_available = True
    except ImportError:
        logger.warning("winsound module not available, sound notifications disabled")
        ENABLE_SOUND_NOTIFICATION = False
else:
    logger.info("Sound notifications only supported on Windows")
    ENABLE_SOUND_NOTIFICATION = False


def play_notification_sound(sound_name: Optional[Union[str, list]] = None, frequency: int = 800, duration: int = 200) -> None:
    """
    Play a notification sound when AI processing is complete.
    
    Args:
        sound_name: Can be:
            - System sound name (e.g., "SystemAsterisk")
            - Path to a WAV file (e.g., "sounds/success.wav")
            - List of [frequency, duration] pairs for beep pattern (e.g., [[800, 100], [1000, 100]])
            - None to use config default or single beep
        frequency: Frequency for beep sound (Hz) if using beep. Default is 800Hz.
        duration: Duration for beep sound (ms) if using beep. Default is 200ms.
    """
    if not ENABLE_SOUND_NOTIFICATION:
        return
    
    if not _winsound_available:
        return
    
    # Use provided sound name or fall back to configured default
    sound_to_play = sound_name or NOTIFICATION_SOUND
    
    try:
        if isinstance(sound_to_play, list):
            # Play beep pattern
            for freq, dur in sound_to_play:
                winsound.Beep(freq, dur)
        elif sound_to_play and os.path.exists(sound_to_play):
            # Play WAV file
            winsound.PlaySound(sound_to_play, winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sound_to_play and not sound_to_play.endswith('.wav'):
            # Try as system sound
            winsound.PlaySound(sound_to_play, winsound.SND_ALIAS | winsound.SND_ASYNC)
        else:
            # Use simple beep if no sound specified
            winsound.Beep(frequency, duration)
    except Exception as e:
        logger.debug(f"Failed to play sound '{sound_to_play}': {e}")
        try:
            # Fallback to simple beep
            winsound.Beep(frequency, duration)
        except Exception as e2:
            logger.debug(f"Failed to play beep: {e2}")


def play_error_sound() -> None:
    """Play an error notification sound - descending tone pattern."""
    # Descending pattern for error
    play_notification_sound([[800, 150], [600, 150], [400, 200]])


def play_success_sound() -> None:
    """Play a success notification sound - ascending tone pattern."""
    # Pleasant ascending pattern for success
    play_notification_sound([[523, 100], [659, 100], [784, 150]])


def play_warning_sound() -> None:
    """Play a warning notification sound - two-tone alert."""
    # Two-tone alert pattern
    play_notification_sound([[700, 150], [700, 150]]) 