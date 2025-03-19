"""
Test script for the keyboard-first popup window UI.
"""
from ui.popup_window import PopupWindow
import sys
import pyperclip
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtTest import QTest

def main():
    """Test the keyboard-first popup window UI"""
    print("Starting keyboard-first UI test")
    app = QApplication(sys.argv)
    
    # Test data
    test_text = "This is a test of the keyboard-first UI."
    pyperclip.copy(test_text)
    print(f"Set clipboard to: '{test_text}'")
    
    # Create and show window
    window = PopupWindow()
    window.set_input_text(test_text)
    window.show()
    print("Window shown")
    
    # Simulate a sequence of keyboard interactions (for demonstration only)
    def run_test_sequence():
        # Short delay to ensure window is ready
        QTimer.singleShot(500, lambda: test_keyboard_navigation(window))
    
    # Start the test sequence after a delay
    QTimer.singleShot(1000, run_test_sequence)
    
    # Auto-close after the tests
    QTimer.singleShot(5000, app.quit)
    
    # Start the event loop
    app.exec_()
    
    print("Test completed")
    return 0

def test_keyboard_navigation(window):
    """Test keyboard navigation in the window"""
    print("\nTesting keyboard navigation...")
    
    # Test 'h' key to toggle hints
    print("Testing 'h' key to toggle hints")
    # First, make sure we're in navigate mode
    window.text_tab.enter_navigate_mode()
    # Now send the 'h' key
    QTest.keyClick(window, Qt.Key_H)
    print("Pressed 'h' key - hint visibility should toggle")
    
    # Test 'c' key for correction
    print("Testing 'c' key for correction")
    QTest.keyClick(window, Qt.Key_C)
    print("Pressed 'c' key - correction action should run")
    
    # Test typing in the dropdown for filtering
    print("Testing dropdown filtering")
    window.text_tab.prompt_dropdown.setFocus()
    QTest.keyClicks(window.text_tab.prompt_dropdown, "conver")
    print("Typed 'conver' in dropdown - should filter to conversation prompts")
    
    # Test Escape key
    print("Testing Escape key")
    QTest.keyClick(window, Qt.Key_Escape)
    print("Pressed Escape key - should exit edit mode or prepare to close")
    
    print("Keyboard navigation test completed")

if __name__ == "__main__":
    sys.exit(main()) 