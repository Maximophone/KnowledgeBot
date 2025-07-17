"""Test the sound notification functionality"""
import time
import sys
import os

# Add parent directory to path to import from obsidian module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obsidian.notification_utils import (
    play_notification_sound, 
    play_error_sound, 
    play_success_sound, 
    play_warning_sound,
    ENABLE_SOUND_NOTIFICATION
)

def test_sound_notifications():
    """Test that sound notifications work properly"""
    
    if not ENABLE_SOUND_NOTIFICATION:
        print("Sound notifications are disabled in configuration or not supported on this platform")
        return
    
    print("Testing sound notifications...")
    print("\n=== PLEASANT BEEP PATTERNS ===")
    
    try:
        # Test 1: Default notification from config
        print("\n1. Playing default notification (from config)...")
        play_notification_sound()
        time.sleep(1)
        
        # Test 2: Musical patterns
        print("\n2. Testing pleasant musical patterns:")
        
        print("   a) Single A note (440Hz)...")
        play_notification_sound([[440, 200]])
        time.sleep(0.8)
        
        print("   b) C-E-G major chord...")
        play_notification_sound([[523, 100], [659, 100], [784, 150]])
        time.sleep(0.8)
        
        print("   c) Perfect fifth (G-C)...")
        play_notification_sound([[392, 100], [523, 150]])
        time.sleep(0.8)
        
        print("   d) Gentle bell pattern...")
        play_notification_sound([[800, 50], [800, 50], [0, 50], [800, 100]])
        time.sleep(0.8)
        
        # Test 3: Semantic sounds (new pleasant versions)
        print("\n3. Testing semantic notification sounds:")
        
        print("   Success (ascending tones)...")
        play_success_sound()
        time.sleep(1)
        
        print("   Error (descending tones)...")
        play_error_sound()
        time.sleep(1)
        
        print("   Warning (two-tone alert)...")
        play_warning_sound()
        time.sleep(1)
        
        # Test 4: Custom WAV file (if exists)
        print("\n4. Testing custom WAV file support:")
        test_wav = "sounds/notification.wav"
        if os.path.exists(test_wav):
            print(f"   Playing {test_wav}...")
            play_notification_sound(test_wav)
        else:
            print(f"   No custom WAV found at {test_wav}")
            print("   Place a WAV file there to test custom sounds!")
        
        time.sleep(0.5)
        
        # Test 5: Comparison with system sounds
        print("\n5. For comparison - Windows system sounds:")
        print("   (These are the 'unbearable' ones)")
        
        for sound in ["SystemAsterisk", "SystemHand"]:
            print(f"   {sound}...")
            play_notification_sound(sound)
            time.sleep(0.8)
        
        print("\n✨ All sound tests completed!")
        print("\nTo use better sounds, edit config/user_config.py")
        print("or place WAV files in the sounds/ folder")
        
    except Exception as e:
        print(f"Error during sound test: {e}")

if __name__ == "__main__":
    test_sound_notifications() 