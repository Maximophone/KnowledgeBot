"""
Popup Window Module

This module provides a keyboard-focused interface for text processing with AI models.

Key features:
- Single-key shortcuts for common actions
- Type-ahead filtering for prompt selection
- Toggleable keyboard shortcut hints with 'h' key
- Streamlined workflow optimized for keyboard users
- Backward compatibility with previous versions

Implementation notes:
- Keyboard event handling prioritizes direct key access
- Focus management ensures logical navigation with Tab key
- Type-ahead filtering efficiently handles large prompt libraries
- Shortcut hints can be toggled for cleaner UI or better discoverability

Compatibility notes:
- The FilterableComboBox implementation avoids using QComboBox.CompleterPopupCompletionMode
  which may not exist in older PyQt5 versions
- Safety checks were added around completer access to prevent attribute errors
- Error handling has been improved to catch potential compatibility issues
"""

from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
                         QTextEdit, QLabel, QShortcut, QComboBox, QApplication, QTabWidget,
                         QSplitter, QStatusBar, QLineEdit, QCheckBox, QFrame, QToolTip, QCompleter)
from PyQt5.QtGui import QKeySequence, QFont, QColor, QPalette
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
import os
import pyperclip
from ai import AI, get_prompt
from ai.types import Message, MessageContent
from config.paths import PATHS
import sys

ai_model = AI("haiku3.5")

# Define a dictionary to map keys to their corresponding actions
# Format: 'key': ('action_name', 'description')
ACTIONS = {
    'c': ('correction', 'Correct text grammar and spelling'),
    'i': ('light_improvement', 'Lightly improve the writing'),
    'f': ('conversation_format', 'Format as a conversation'),
    'p': ('custom_prompt', 'Use custom prompt'),
    'h': ('toggle_hints', 'Toggle keyboard shortcut hints'),
    'Escape': ('close', 'Close the window'),
    'Ctrl+Return': ('copy_and_close', 'Copy text and close'),
}

class FilterableComboBox(QComboBox):
    """ComboBox with type-ahead filtering capability
    
    Implementation notes:
    - This class simplifies QComboBox's completer settings to avoid version compatibility issues
    - It handles direct filtering through a custom mechanism rather than relying on Qt's completer
    - Key events are captured to provide better keyboard navigation specifically for filtering
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        # Simplify completer settings to avoid compatibility issues
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

class KeyboardFocusFrame(QFrame):
    """Frame that shows a highlight when it has keyboard focus"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Plain)
        self.setLineWidth(1)
        self.setMidLineWidth(0)
        
    def focusInEvent(self, event):
        """Handle focus in event with visual feedback"""
        self.setStyleSheet("border: 2px solid #4A90E2;")
        super().focusInEvent(event)
        
    def focusOutEvent(self, event):
        """Handle focus out event"""
        self.setStyleSheet("")
        super().focusOutEvent(event)

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

def load_prompts(directory):
    """Load all prompt files from the prompt directory"""
    prompts = {}
    try:
        for filename in os.listdir(directory):
            if filename.endswith('.md'):
                with open(os.path.join(directory, filename), 'r', encoding='utf-8') as file:
                    title = filename.split(".md")[0]
                    content = file.read()
                    prompts[title] = {
                        'filename': filename,
                        'content': content
                    }
    except Exception as e:
        print(f"Error loading prompts: {e}")
    return prompts

class TextTab(QWidget):
    """Tab for text processing functionality with keyboard-first focus"""
    
    status_message = pyqtSignal(str)
    mode_changed = pyqtSignal(str)
    
    def __init__(self, prompts, parent=None):
        super().__init__(parent)
        self.prompts = prompts
        # Initialize all instance attributes that will be used later
        self.prompt_dropdown = None
        self.input_text = None
        self.prompt_text = None
        self.action_buttons = {}
        self.show_hints = True
        self.mode = "Navigate"  # Can be Navigate or Edit
        # Now set up the UI
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Create the splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)
        
        # Upper section with prompt selection and text area
        upper_widget = QWidget()
        upper_layout = QVBoxLayout(upper_widget)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        
        # Prompt selection area
        prompt_layout = QHBoxLayout()
        
        # Create the dropdown first
        prompt_label = QLabel("Prompt:")
        self.prompt_dropdown = FilterableComboBox()
        self.prompt_dropdown.add_items(list(self.prompts.keys()))
        self.prompt_dropdown.activated.connect(self.load_selected_prompt)
        prompt_label.setBuddy(self.prompt_dropdown)
        
        prompt_layout.addWidget(prompt_label)
        prompt_layout.addWidget(self.prompt_dropdown, 1)
        
        # Add to upper layout
        upper_layout.addLayout(prompt_layout)
        
        # Text input area
        self.input_text_edit = QTextEdit()
        self.input_text_edit.setReadOnly(False)  # Explicitly set to editable
        self.input_text_edit.setPlaceholderText("Enter your text here...")
        input_label = QLabel("Input Text:")
        input_label.setBuddy(self.input_text_edit)
        
        # Connect focus events to update mode
        self.input_text_edit.focusInEvent = lambda e: self.enter_edit_mode(e)
        
        upper_layout.addWidget(input_label)
        upper_layout.addWidget(self.input_text_edit, 1)
        
        # Lower section with prompt text and actions
        lower_widget = QWidget()
        lower_layout = QVBoxLayout(lower_widget)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        
        # Prompt text area
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Prompt will appear here...")
        prompt_text_label = QLabel("Prompt Text:")
        prompt_text_label.setBuddy(self.prompt_text)
        
        # Connect focus events to update mode
        self.prompt_text.focusInEvent = lambda e: self.enter_edit_mode(e)
        
        lower_layout.addWidget(prompt_text_label)
        lower_layout.addWidget(self.prompt_text, 1)
        
        # Actions section
        actions_layout = QHBoxLayout()
        
        # Create action buttons with shortcut hints
        action_keys = ['c', 'i', 'f', 'p']
        for key in action_keys:
            action_name, action_desc = ACTIONS[key]
            btn = ActionButton(action_name.replace('_', ' ').title(), key)
            btn.setToolTip(action_desc)
            btn.clicked.connect(lambda checked, k=key: self.process_key_action(k))
            self.action_buttons[key] = btn
            actions_layout.addWidget(btn)
        
        lower_layout.addLayout(actions_layout)
        
        # Add upper and lower widgets to splitter
        splitter.addWidget(upper_widget)
        splitter.addWidget(lower_widget)
        
        # Set initial sizes
        splitter.setSizes([200, 200])
        
        # Add splitter to main layout
        layout.addWidget(splitter)
        
        # Keyboard mode indicator
        mode_layout = QHBoxLayout()
        self.mode_label = QLabel("Mode: Navigate")
        mode_layout.addWidget(self.mode_label)
        
        # Shortcut hints toggle
        self.hint_checkbox = QCheckBox("Show Keyboard Shortcuts")
        self.hint_checkbox.setChecked(self.show_hints)
        self.hint_checkbox.stateChanged.connect(self.toggle_hints)
        mode_layout.addWidget(self.hint_checkbox)
        
        mode_layout.addStretch(1)
        layout.addLayout(mode_layout)
        
        # Load the first prompt automatically
        self.load_selected_prompt()
        
        # Set initial focus to input text
        QTimer.singleShot(100, self.input_text_edit.setFocus)
    
    def enter_edit_mode(self, event):
        """Enter edit mode when a text edit gets focus"""
        if self.mode != "Edit":
            self.mode = "Edit"
            self.mode_label.setText("Mode: Edit")
            self.mode_changed.emit("Edit")
        # Call the original focusInEvent
        QTextEdit.focusInEvent(self.input_text_edit, event)
    
    def enter_navigate_mode(self):
        """Enter navigate mode for keyboard navigation"""
        if self.mode != "Navigate":
            self.mode = "Navigate"
            self.mode_label.setText("Mode: Navigate")
            self.mode_changed.emit("Navigate")
            # Remove focus from text edits
            if self.input_text_edit.hasFocus() or self.prompt_text.hasFocus():
                self.setFocus()
    
    def toggle_hints(self, state):
        """Toggle visibility of keyboard shortcut hints"""
        self.show_hints = (state == Qt.Checked)
        # Update all buttons
        for btn in self.action_buttons.values():
            btn.set_show_hints(self.show_hints)
        
        self.status_message.emit("Keyboard hints " + ("shown" if self.show_hints else "hidden"))
    
    def process_key_action(self, key):
        """Process an action triggered by a keyboard shortcut"""
        if key == 'h':
            # Toggle hints
            self.hint_checkbox.setChecked(not self.hint_checkbox.isChecked())
            return
            
        if key in ['c', 'i', 'f']:
            # Predefined prompt
            action_name = ACTIONS[key][0]
            self.perform_action(action_name)
        elif key == 'p':
            # Custom prompt
            self.perform_action('custom_prompt')
    
    def keyPressEvent(self, event):
        """Handle key press events for keyboard shortcuts"""
        key = event.key()
        
        # In Navigate mode, single letter keys trigger actions
        if self.mode == "Navigate":
            key_text = chr(key).lower()
            if key_text in ACTIONS:
                self.process_key_action(key_text)
                return
                
        # Mode switching
        if key == Qt.Key_Escape:
            if self.mode == "Edit":
                self.enter_navigate_mode()
                return
            
        # Tab key handling for improved navigation
        if key == Qt.Key_Tab:
            # Override tab behavior for better navigation
            focused_widget = QApplication.focusWidget()
            if focused_widget == self.prompt_dropdown:
                self.input_text_edit.setFocus()
            elif focused_widget == self.input_text_edit:
                self.prompt_text.setFocus()
            elif focused_widget == self.prompt_text:
                # Find the first action button
                if self.action_buttons:
                    next(iter(self.action_buttons.values())).setFocus()
            return
            
        super().keyPressEvent(event)
    
    def load_selected_prompt(self):
        """Load the selected prompt into the prompt text area"""
        try:
            current_prompt = self.prompt_dropdown.currentText()
            if not current_prompt:
                self.status_message.emit("No prompt selected")
                return
            
            if current_prompt in self.prompts:
                self.prompt_text.setPlainText(self.prompts[current_prompt]['content'])
                self.status_message.emit(f"Loaded prompt: {current_prompt}")
            else:
                self.status_message.emit(f"Prompt '{current_prompt}' not found")
        except Exception as e:
            self.status_message.emit(f"Error loading prompt: {str(e)}")
    
    def perform_action(self, action_name):
        """Process the text based on the selected action"""
        text = self.input_text_edit.toPlainText()
        
        if not text:
            self.status_message.emit("No text to process")
            return
        
        try:
            if action_name == "custom_prompt":
                prompt = self.prompt_text.toPlainText() + "\n\n"
            else:
                prompt = get_prompt(action_name)
                self.prompt_text.setPlainText(prompt)
                
            message = Message(
                role="user",
                content=[MessageContent(
                    type="text",
                    text=prompt + text
                )]
            )
            
            self.status_message.emit(f"Processing text with {action_name}...")
            new_text = ai_model.message(message).content
            self.input_text_edit.setPlainText(new_text)
            pyperclip.copy(new_text)
            self.status_message.emit(f"Text processed and copied to clipboard")
            
        except Exception as e:
            self.status_message.emit(f"Error: {str(e)}")

class SettingsTab(QWidget):
    """Tab for application settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Keyboard hints section
        keyboard_section = QWidget()
        keyboard_layout = QVBoxLayout(keyboard_section)
        
        keyboard_label = QLabel("Keyboard Settings")
        keyboard_label.setFont(QFont("Arial", 12, QFont.Bold))
        keyboard_layout.addWidget(keyboard_label)
        
        # Default hints setting
        self.default_hints = QCheckBox("Show keyboard hints by default")
        self.default_hints.setChecked(True)
        keyboard_layout.addWidget(self.default_hints)
        
        # Add help text
        help_text = QLabel(
            "Keyboard Shortcuts:\n"
            "- Press 'h' to toggle shortcut hints\n"
            "- Press 'c' for correction\n"
            "- Press 'i' for improvement\n"
            "- Press 'f' for conversation format\n"
            "- Press 'p' to use custom prompt\n"
            "- Press 'Escape' to exit edit mode or close\n"
            "- Press 'Ctrl+Enter' to copy and close"
        )
        help_text.setWordWrap(True)
        keyboard_layout.addWidget(help_text)
        
        # Model settings section
        model_section = QWidget()
        model_layout = QVBoxLayout(model_section)
        
        model_label = QLabel("AI Model Settings")
        model_label.setFont(QFont("Arial", 12, QFont.Bold))
        model_layout.addWidget(model_label)
        
        model_selection = QHBoxLayout()
        model_selection.addWidget(QLabel("Default Model:"))
        
        self.model_dropdown = QComboBox()
        self.model_dropdown.addItems(["haiku3.5", "gpt-4", "claude-3-opus"])
        model_selection.addWidget(self.model_dropdown)
        
        model_layout.addLayout(model_selection)
        
        # Add sections to main layout
        layout.addWidget(keyboard_section)
        layout.addWidget(model_section)
        layout.addStretch(1)  # Push everything to the top

class PopupWindow(QMainWindow):
    """Main application window with tabbed interface"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Text Processor")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setGeometry(100, 100, 800, 600)
        
        # Load prompts
        self.prompts = load_prompts(PATHS.prompts_library)
        
        # Set up the central widget with tabs
        self.setup_ui()
    
    def setup_ui(self):
        # Create the central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Add tabs
        self.text_tab = TextTab(self.prompts)
        self.text_tab.status_message.connect(self.update_status)
        self.text_tab.mode_changed.connect(self.update_mode)
        self.tab_widget.addTab(self.text_tab, "Text Processing")
        
        self.settings_tab = SettingsTab()
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        # Add tab widget to layout
        layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Press 'h' to toggle keyboard shortcuts")
        
        # Set up global keyboard events
        self.setup_keyboard_handlers()
    
    def update_mode(self, mode):
        """Update the window mode indicator"""
        self.update_status(f"Mode: {mode}")
    
    def setup_keyboard_handlers(self):
        """Set up global keyboard handlers"""
        # Escape to close
        escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        escape_shortcut.activated.connect(self.handle_escape)
        
        # Ctrl+Enter to copy and close
        copy_close_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        copy_close_shortcut.activated.connect(self.copy_and_close)
        
        # Tab navigation
        for i in range(1, min(10, self.tab_widget.count() + 1)):
            index = i - 1
            alt_shortcut = QShortcut(QKeySequence(f"Alt+{i}"), self)
            alt_shortcut.activated.connect(lambda idx=index: self.tab_widget.setCurrentIndex(idx))
    
    def handle_escape(self):
        """Handle Escape key press"""
        if self.text_tab.mode == "Edit":
            # First escape exits edit mode
            self.text_tab.enter_navigate_mode()
        else:
            # Second escape closes window
            self.close()
    
    def copy_and_close(self):
        """Copy the current text and close the window"""
        text = self.text_tab.input_text_edit.toPlainText()
        if text:
            pyperclip.copy(text)
            self.update_status("Text copied to clipboard")
            QTimer.singleShot(500, self.close)  # Close after a short delay to show status
        else:
            self.update_status("No text to copy")
    
    def keyPressEvent(self, event):
        """Handle global key press events"""
        key = event.key()
        
        # h key to toggle hints when in navigate mode
        if key == Qt.Key_H and self.text_tab.mode == "Navigate":
            self.text_tab.toggle_hints(not self.text_tab.show_hints)
            return
            
        super().keyPressEvent(event)
    
    def update_status(self, message):
        """Update the status bar with a message"""
        self.status_bar.showMessage(message, 5000)  # Show for 5 seconds
        
    @property
    def input_text_area(self):
        # Ensure this returns the editable text area
        return self.text_tab.input_text_edit
        
    @property
    def prompt_text_area(self):
        """Backward compatibility for accessing the prompt text area"""
        return self.text_tab.prompt_text
        
    def set_input_text(self, text):
        """Set the input text content"""
        self.text_tab.input_text_edit.setPlainText(text)
        
    def get_input_text(self):
        """Get the input text content"""
        return self.text_tab.input_text_edit.toPlainText()
        
    def set_prompt_text(self, text):
        """Set the prompt text content"""
        self.text_tab.prompt_text.setPlainText(text)
        
    def get_prompt_text(self):
        """Get the prompt text content"""
        return self.text_tab.prompt_text.toPlainText() 