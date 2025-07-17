# Sound Notifications

The KnowledgeBot includes sound notification capabilities to provide audio feedback when AI processing completes.

## Configuration

Sound notifications can be configured in `config/user_config.py`:

```python
# Enable/disable sound notifications
ENABLE_AI_COMPLETION_SOUND = True

# Set the default notification sound
AI_COMPLETION_SOUND = "SystemAsterisk"  # Or None for a simple beep
```

## Available System Sounds (Windows)

- `SystemAsterisk` - Default notification
- `SystemExclamation` - Warning/attention sound  
- `SystemExit` - Exit/close sound
- `SystemHand` - Error/stop sound
- `SystemQuestion` - Question/query sound
- `None` - Simple beep (800Hz, 200ms)

## Using Sound Notifications in Code

The notification utilities are available in `obsidian/notification_utils.py`:

```python
from obsidian.notification_utils import (
    play_notification_sound,  # Generic notification
    play_success_sound,       # Success completion
    play_error_sound,         # Error occurred
    play_warning_sound        # Warning/attention needed
)

# Play the default configured sound
play_notification_sound()

# Play a specific system sound
play_notification_sound("SystemExclamation")

# Play a custom beep
play_notification_sound(None, frequency=1000, duration=300)

# Use semantic notification functions
play_success_sound()  # Plays a success tone
play_error_sound()    # Plays an error tone
play_warning_sound()  # Plays a warning tone
```

## Integration Example

Here's how the AI processing uses notifications:

```python
try:
    # Process AI request...
    result = process_ai_request()
    play_notification_sound()  # Success!
    return result
except Exception as e:
    play_error_sound()  # Alert user to error
    raise
```

## Platform Support

Sound notifications are currently only supported on Windows using the built-in `winsound` module. On other platforms, the notification functions will silently do nothing.

## Testing

To test sound notifications:

```bash
python tests/test_sound_notification.py
```

This will play various notification sounds to verify your configuration. 