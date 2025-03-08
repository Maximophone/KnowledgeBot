"""
Keyboard Listener Module

This module provides a system-wide hotkey (Ctrl+.) to trigger the popup window
for text processing. It handles clipboard integration and ensures the window
appears properly in focus.

Implementation notes:
- Robust error handling with fallback methods for key operations
- Comprehensive logging to help diagnose any issues
- Safe window activation and focus management

Compatibility considerations:
- Some PyQt5 versions may have issues with certain methods, so fallbacks are provided
- The show_popup function uses multiple layers of error handling to ensure stability
- Error conditions are logged in detail to help with troubleshooting
"""

import asyncio
import keyboard
import pyperclip
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from ui.popup_window import PopupWindow
from config.logging_config import setup_logger

logger = setup_logger(__name__)

def show_popup(test_mode=False):
    """
    Show the popup window with the clipboard contents.
    
    This function handles creating the QApplication, setting up the window,
    and managing potential compatibility issues with different PyQt versions.
    Multiple fallback mechanisms are in place to ensure reliability.
    
    Args:
        test_mode (bool): If True, will automatically close after 2 seconds.
    """
    try:
        # Create QApplication
        app = QApplication([])
        
        # Create and configure window
        window = PopupWindow()
        
        # Handle potential compatibility issues safely
        try:
            window.set_input_text(pyperclip.paste())
        except Exception as e:
            logger.error(f"Error setting input text: {str(e)}")
            # Fallback method if needed
            try:
                window.text_tab.input_text.setPlainText(pyperclip.paste())
            except Exception as inner_e:
                logger.error(f"Fallback method also failed: {str(inner_e)}")
        
        # Activate window and set focus
        try:
            window.activateWindow()
            window.text_tab.input_text.setFocus()
        except Exception as e:
            logger.error(f"Error setting focus: {str(e)}")
        
        # Show window
        window.show()
        logger.info("Popup window displayed successfully")
        
        # Auto-close in test mode
        if test_mode:
            logger.info("Test mode active - will close automatically after 2 seconds")
            QTimer.singleShot(2000, app.quit)
        
        # Start event loop
        app.exec_()
        
        return window  # Return the window for testing purposes
    
    except Exception as e:
        logger.error(f"Failed to show popup: {str(e)}")
        return None

async def main():
    """Main function to listen for the keyboard shortcut and show the popup"""
    hotkey = 'ctrl+.'
    logger.info("Listening for hotkey %s", hotkey)
    
    # Register the hotkey
    try:
        keyboard.add_hotkey(hotkey, show_popup)
        logger.info("Hotkey registered successfully")
    except Exception as e:
        logger.error(f"Failed to register hotkey: {str(e)}")
        return

    try:
        logger.info("Waiting for hotkey to be pressed...")
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}")
    finally:
        logger.info("Exiting...")

if __name__ == "__main__":
    asyncio.run(main()) 