"""
Standalone test script for the keyboard-first UI concept
"""
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                          QWidget, QPushButton, QTextEdit, QLabel, QComboBox,
                          QCheckBox, QFrame, QStatusBar)
from PyQt5.QtCore import Qt, QTimer

class FilterableComboBox(QComboBox):
    """ComboBox with type-ahead filtering capability"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setFocusPolicy(Qt.StrongFocus)
        self.lineEdit().textEdited.connect(self.filter_items)
        self.original_items = []
        
    def add_items(self, items):
        """Add items and keep track of the original list"""
        self.original_items = items
        self.addItems(items)
    
    def filter_items(self, text):
        """Filter the items based on the current text"""
        if not text:
            # If text is empty, restore all items
            self.clear()
            self.addItems(self.original_items)
            return
            
        # Filter items that contain the typed text
        self.clear()
        filtered_items = [item for item in self.original_items if text.lower() in item.lower()]
        self.addItems(filtered_items)
        self.showPopup()
    
    def keyPressEvent(self, event):
        """Override key press event for better keyboard navigation"""
        key = event.key()
        if key == Qt.Key_Escape:
            # Reset filter and hide popup
            self.lineEdit().clear()
            self.filter_items("")
            self.hidePopup()
            event.accept()
        elif key == Qt.Key_Return or key == Qt.Key_Enter:
            # Activate the selected item
            self.activated.emit(self.currentIndex())
            self.hidePopup()
            event.accept()
        else:
            super().keyPressEvent(event)

class ActionButton(QPushButton):
    """Button with built-in shortcut hint display"""
    
    def __init__(self, text, shortcut_key, parent=None):
        super().__init__(text, parent)
        self.shortcut_key = shortcut_key
        self.show_hints = True
        self.base_text = text
        self.update_text()
        
    def update_text(self):
        """Update button text based on hint visibility"""
        if self.show_hints:
            self.setText(f"{self.base_text} ({self.shortcut_key})")
        else:
            self.setText(self.base_text)
    
    def set_show_hints(self, show):
        """Set whether to show shortcut hints"""
        if show != self.show_hints:
            self.show_hints = show
            self.update_text()

class SimpleKeyboardUI(QMainWindow):
    """Simple keyboard-first UI for testing purposes"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Keyboard-First UI Test")
        self.setGeometry(100, 100, 800, 600)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Input section
        input_layout = QVBoxLayout()
        input_label = QLabel("Input Text:")
        input_layout.addWidget(input_label)
        
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Enter your text here...")
        input_layout.addWidget(self.input_text)
        layout.addLayout(input_layout)
        
        # Dropdown for prompts
        prompt_layout = QHBoxLayout()
        prompt_label = QLabel("Select Prompt:")
        prompt_layout.addWidget(prompt_label)
        
        self.prompt_dropdown = FilterableComboBox()
        self.prompt_dropdown.add_items([
            "correction", 
            "light_improvement", 
            "conversation_format", 
            "custom_prompt",
            "summarize",
            "rewrite",
            "simplify"
        ])
        prompt_layout.addWidget(self.prompt_dropdown, 1)
        layout.addLayout(prompt_layout)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        self.create_action_button(buttons_layout, "Correction", "c", lambda: self.show_message("Correction action triggered"))
        self.create_action_button(buttons_layout, "Improvement", "i", lambda: self.show_message("Improvement action triggered"))
        self.create_action_button(buttons_layout, "Format", "f", lambda: self.show_message("Format action triggered"))
        self.create_action_button(buttons_layout, "Custom", "p", lambda: self.show_message("Custom action triggered"))
        layout.addLayout(buttons_layout)
        
        # Hint toggle
        hint_layout = QHBoxLayout()
        self.hint_checkbox = QCheckBox("Show Keyboard Shortcuts")
        self.hint_checkbox.setChecked(True)
        self.hint_checkbox.stateChanged.connect(self.toggle_hints)
        hint_layout.addWidget(self.hint_checkbox)
        hint_layout.addStretch(1)
        layout.addLayout(hint_layout)
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Press 'h' to toggle keyboard shortcuts")
        
        # Store action buttons
        self.action_buttons = {}
        
        # Initial focus
        self.input_text.setFocus()
        
    def create_action_button(self, layout, text, shortcut_key, action):
        """Create an action button with shortcut hint"""
        button = ActionButton(text, shortcut_key)
        button.clicked.connect(action)
        layout.addWidget(button)
        self.action_buttons[shortcut_key] = button
        return button
        
    def show_message(self, message):
        """Show a message in the status bar"""
        self.status_bar.showMessage(message, 3000)
        
    def toggle_hints(self, state):
        """Toggle visibility of keyboard shortcut hints"""
        show_hints = (state == Qt.Checked)
        for button in self.action_buttons.values():
            button.set_show_hints(show_hints)
        
        self.show_message("Keyboard hints " + ("shown" if show_hints else "hidden"))
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        key = event.key()
        
        # Handle single-key shortcuts
        if key == Qt.Key_C:
            self.show_message("Pressed 'c' key - Correction")
            return
        elif key == Qt.Key_I:
            self.show_message("Pressed 'i' key - Improvement")
            return
        elif key == Qt.Key_F:
            self.show_message("Pressed 'f' key - Format")
            return
        elif key == Qt.Key_P:
            self.show_message("Pressed 'p' key - Custom prompt")
            return
        elif key == Qt.Key_H:
            # Toggle hints
            self.hint_checkbox.setChecked(not self.hint_checkbox.isChecked())
            return
        elif key == Qt.Key_Escape:
            self.close()
            return
            
        super().keyPressEvent(event)

def main():
    """Run the test application"""
    print("Starting keyboard-first UI test")
    app = QApplication(sys.argv)
    
    window = SimpleKeyboardUI()
    window.show()
    print("Test window shown")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 