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
    
    Args:
        test_mode (bool): If True, will automatically close after 2 seconds.
    """
    app = QApplication([])
    window = PopupWindow()
    
    # Access the input text through the text_tab or use the convenience property
    window.input_text_area.setPlainText(pyperclip.paste())
    window.activateWindow()
    window.show()
    
    # Auto-close in test mode
    if test_mode:
        logger.info("Test mode active - will close automatically after 2 seconds")
        QTimer.singleShot(2000, app.quit)
    
    app.exec_()
    
    return window  # Return the window for testing purposes

async def main():
    hotkey = 'ctrl+.'
    logger.info("Listening for hotkey %s", hotkey)
    # Register the hotkey
    keyboard.add_hotkey(hotkey, show_popup)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Exiting...")

if __name__ == "__main__":
    asyncio.run(main()) 