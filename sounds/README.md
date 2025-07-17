# Custom Notification Sounds

This folder is for custom notification sounds. The system supports WAV files for better audio feedback.

## Quick Setup for Better Sounds

### Option 1: Download Free Sounds (Recommended)

Visit these sites for pleasant notification sounds:
- **Freesound.org** - Search for "notification", "bell", or "chime"
- **Zapsplat.com** - Free sounds with account (great UI sounds)
- **Notification Sounds** - https://notificationsounds.com/notification-sounds
- **Material Design Sounds** - Google's pleasant UI sounds

Good search terms: "gentle bell", "soft chime", "ui notification", "success sound"

### Option 2: Create Your Own

Use Audacity (free) or any audio editor to:
1. Generate a tone (Generate → Tone)
2. Apply fade in/out effects
3. Export as WAV

### Option 3: Use Pleasant Beep Patterns

No downloads needed! Edit `config/user_config.py`:

```python
# Musical notes (frequency in Hz)
# C=262, D=294, E=330, F=349, G=392, A=440, B=494, C5=523

# Pleasant patterns:
AI_COMPLETION_SOUND = [[440, 200]]  # Single A note
AI_COMPLETION_SOUND = [[523, 100], [659, 100], [784, 150]]  # C-E-G chord
AI_COMPLETION_SOUND = [[392, 100], [523, 150]]  # G-C perfect fifth
AI_COMPLETION_SOUND = [[659, 80], [659, 80], [659, 80]]  # Triple E note
```

## Using Custom Sounds

1. Place your WAV file in this `sounds/` folder
2. Update `config/user_config.py`:
   ```python
   AI_COMPLETION_SOUND = "sounds/your-sound.wav"
   ```

## Recommended Sounds

For the least "unbearable" experience:
- Short duration (under 500ms)
- Mid-range frequencies (400-800 Hz)
- Gentle attack/decay (no harsh starts)
- Single tone or ascending pattern (not descending)

## Test Your Sounds

```bash
python tests/test_sound_notification.py
``` 