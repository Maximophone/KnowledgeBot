from ui.popup_window import PopupWindow
import sys
import pyperclip
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

def main():
    print("Starting test")
    app = QApplication(sys.argv)
    
    # Test some text
    test_text = "Simple popup test"
    pyperclip.copy(test_text)
    print(f"Set clipboard to: '{test_text}'")
    
    # Create window
    window = PopupWindow()
    
    # Test direct access to input_text_area (the compatibility property)
    window.input_text_area.setPlainText(test_text)
    print("Set text using input_text_area property")
    
    # Show window
    window.show()
    print("Window shown")
    
    # Auto-close after 2 seconds
    QTimer.singleShot(2000, app.quit)
    
    print("Running app...")
    app.exec_()
    print("App completed")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 