import asyncio
import keyboard
import pyperclip
from PyQt5.QtWidgets import QApplication
from ui.popup_window import PopupWindow
from config.logging_config import setup_logger

logger = setup_logger(__name__)

def show_popup():
    app = QApplication([])
    window = PopupWindow()
    window.input_text_area.setPlainText(pyperclip.paste())
    window.activateWindow()
    window.show()
    app.exec_()

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