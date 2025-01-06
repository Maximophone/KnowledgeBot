import asyncio
import keyboard
import pyperclip
from PyQt5.QtWidgets import QApplication
from ui.popup_window import PopupWindow

def show_popup():
    app = QApplication([])
    window = PopupWindow()
    window.input_text_area.setPlainText(pyperclip.paste())
    window.activateWindow()
    window.show()
    app.exec_()

async def main():
    print("Listening for hotkey Ctrl+.", flush=True)
    # Register the hotkey
    keyboard.add_hotkey('ctrl+.', show_popup)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("Exiting...", flush=True)

if __name__ == "__main__":
    asyncio.run(main()) 