from services.keyboard_listener import show_popup
import sys
import pyperclip

def main():
    # Set clipboard content for testing
    test_text = "Testing keyboard listener integration"
    pyperclip.copy(test_text)
    print(f"Copied to clipboard: '{test_text}'")
    
    # Use test_mode=True to automatically close after 2 seconds
    print("Opening popup in test mode (will close after 2 seconds)...")
    window = show_popup(test_mode=True)
    
    print("Popup shown and closed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 