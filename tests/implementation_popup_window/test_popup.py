from ui.popup_window import PopupWindow
import sys
from PyQt5.QtWidgets import QApplication
import traceback
from PyQt5.QtCore import QTimer
import pyperclip

def main():
    try:
        print("Starting application")
        app = QApplication(sys.argv)
        print("Created QApplication")
        
        # Initialize some test content
        test_text = "This is a test of the popup window"
        pyperclip.copy(test_text)
        print(f"Copied test text to clipboard: '{test_text}'")
        
        window = PopupWindow()
        print("Window initialized successfully")
        
        # Test backward compatibility
        print("Testing backward compatibility...")
        
        # Test accessing through property
        window.input_text_area.setPlainText("Testing input text area property")
        window.prompt_text_area.setPlainText("Testing prompt text area property")
        
        # Test using convenience methods
        window.set_input_text("Testing set_input_text method")
        input_text = window.get_input_text()
        print(f"Input text retrieved: '{input_text}'")
        
        window.set_prompt_text("Testing set_prompt_text method")
        prompt_text = window.get_prompt_text()
        print(f"Prompt text retrieved: '{prompt_text}'")
        
        window.show()
        print("Window shown")
        
        # Auto-close after 2 seconds
        QTimer.singleShot(2000, app.quit)
        print("Set auto-close timer")
        
        # Start the event loop
        print("Starting event loop")
        app.exec_()
        print("Event loop ended")
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        print(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 