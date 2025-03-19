"""
Simplified test script for the keyboard-first popup window UI.
"""
import sys
import os
import pyperclip
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QTextEdit, QWidget, QPushButton, QLabel, QComboBox
from PyQt5.QtCore import QTimer, Qt

# Create a simplified test version that doesn't require the actual popup_window module
class SimpleKeyboardUI(QMainWindow):
    """Simplified keyboard-first UI for testing purposes"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Keyboard UI Test")
        self.setGeometry(100, 100, 800, 600)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Input section
        input_label = QLabel("Input Text:")
        layout.addWidget(input_label)
        
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Enter your text here...")
        layout.addWidget(self.input_text)
        
        # Dropdown for prompts
        prompt_layout = QVBoxLayout()
        prompt_label = QLabel("Select Prompt:")
        prompt_layout.addWidget(prompt_label)
        
        self.prompt_dropdown = QComboBox()
        self.prompt_dropdown.addItems(["correction", "light_improvement", "conversation_format", "custom_prompt"])
        prompt_layout.addWidget(self.prompt_dropdown)
        layout.addLayout(prompt_layout)
        
        # Action buttons
        buttons_layout = QVBoxLayout()
        self.create_action_button(buttons_layout, "Correction (c)", lambda: self.show_message("Correction action triggered with 'c' key"))
        self.create_action_button(buttons_layout, "Improvement (i)", lambda: self.show_message("Improvement action triggered with 'i' key"))
        self.create_action_button(buttons_layout, "Format (f)", lambda: self.show_message("Format action triggered with 'f' key"))
        self.create_action_button(buttons_layout, "Custom (p)", lambda: self.show_message("Custom action triggered with 'p' key"))
        self.create_action_button(buttons_layout, "Toggle Hints (h)", lambda: self.show_message("Hints toggled with 'h' key"))
        layout.addLayout(buttons_layout)
        
        # Status label
        self.status_label = QLabel("Ready - Press keys to test shortcuts")
        layout.addWidget(self.status_label)
        
    def create_action_button(self, layout, text, action):
        button = QPushButton(text)
        button.clicked.connect(action)
        layout.addWidget(button)
        
    def show_message(self, message):
        """Show a message in the status label"""
        self.status_label.setText(message)
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        key = event.key()
        if key == Qt.Key_C:
            self.show_message("Pressed 'c' key - Correction")
        elif key == Qt.Key_I:
            self.show_message("Pressed 'i' key - Improvement")
        elif key == Qt.Key_F:
            self.show_message("Pressed 'f' key - Format")
        elif key == Qt.Key_P:
            self.show_message("Pressed 'p' key - Custom prompt")
        elif key == Qt.Key_H:
            self.show_message("Pressed 'h' key - Toggle hints")
        elif key == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
            
    def set_input_text(self, text):
        """Set the input text content"""
        self.input_text.setPlainText(text)

def main():
    """Test the simplified keyboard-first UI"""
    print("Starting simplified keyboard-first UI test")
    app = QApplication(sys.argv)
    
    # Test data
    test_text = "This is a test of the keyboard-first UI."
    pyperclip.copy(test_text)
    print(f"Set clipboard to: '{test_text}'")
    
    # Create and show window
    window = SimpleKeyboardUI()
    window.set_input_text(test_text)
    window.show()
    print("Window shown")
    
    # Auto-close after a delay (for automated testing)
    QTimer.singleShot(10000, app.quit)
    
    # Start the event loop
    app.exec_()
    
    print("Test completed")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 