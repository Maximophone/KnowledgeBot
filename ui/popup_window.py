"""
Popup Window Module

This module provides a tabbed interface for text processing with AI models.

Key features:
- Tabbed interface with Text Processing and Settings tabs
- Keyboard navigable components
- Automatic prompt loading
- Customizable keyboard shortcuts
- Status bar for feedback
- Error handling
- Backward compatibility with previous versions

Implementation notes:
- Attribute initialization order is important to prevent AttributeError
- Lambda functions need proper variable binding to work correctly in loops
- Error handling added to improve robustness
- Backward compatibility properties (input_text_area, prompt_text_area) are provided
  to support existing code that used the old interface
"""

from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
                         QTextEdit, QLabel, QShortcut, QComboBox, QApplication, QTabWidget,
                         QSplitter, QStatusBar, QKeySequenceEdit, QDialog, QLineEdit)
from PyQt5.QtGui import QKeySequence, QIcon, QFont
from PyQt5.QtCore import Qt, QSize, pyqtSignal
import os
import pyperclip
from ai import AI, get_prompt
from ai.types import Message, MessageContent
from config.paths import PATHS
import sys

ai_model = AI("haiku3.5")

# Define a dictionary to map actions to their corresponding functions
ACTIONS = {
    'Ctrl+1': 'correction',
    'Ctrl+2': 'light_improvement',
    'Ctrl+3': 'conversation_format',
    'Ctrl+Q': 'Custom Prompt',
    # Add more actions as needed
}

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

class KeyboardNavigableComboBox(QComboBox):
    """Extended QComboBox with improved keyboard navigation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            # Emit activated signal when Enter is pressed
            self.activated.emit(self.currentIndex())
        elif key == Qt.Key_Up:
            # Move to previous item
            current = self.currentIndex()
            if current > 0:
                self.setCurrentIndex(current - 1)
        elif key == Qt.Key_Down:
            # Move to next item
            current = self.currentIndex()
            if current < self.count() - 1:
                self.setCurrentIndex(current + 1)
        else:
            super().keyPressEvent(event)

class ShortcutEditor(QDialog):
    """Dialog for editing keyboard shortcuts"""
    
    def __init__(self, parent=None, shortcuts=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Shortcuts")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.shortcut_editors = {}
        
        for action, description in shortcuts.items():
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(description))
            
            shortcut_edit = QKeySequenceEdit()
            shortcut_edit.setKeySequence(QKeySequence(action))
            row_layout.addWidget(shortcut_edit)
            
            self.shortcut_editors[description] = shortcut_edit
            layout.addLayout(row_layout)
        
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addLayout(buttons_layout)
    
    def get_shortcuts(self):
        result = {}
        for description, editor in self.shortcut_editors.items():
            result[editor.keySequence().toString()] = description
        return result

class TextTab(QWidget):
    """Tab for text processing functionality"""
    
    status_message = pyqtSignal(str)
    
    def __init__(self, prompts, parent=None):
        super().__init__(parent)
        self.prompts = prompts
        # Initialize all instance attributes that will be used later
        self.prompt_dropdown = None
        self.input_text = None
        self.prompt_text = None
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
        self.prompt_dropdown = KeyboardNavigableComboBox()
        self.prompt_dropdown.addItems(self.prompts.keys())
        self.prompt_dropdown.setCurrentIndex(0)
        self.prompt_dropdown.activated.connect(self.load_selected_prompt)
        
        # Now create the label and set the buddy
        prompt_label = QLabel("Prompt:")
        prompt_label.setBuddy(self.prompt_dropdown)
        
        prompt_layout.addWidget(prompt_label)
        prompt_layout.addWidget(self.prompt_dropdown, 1)
        
        # Add to upper layout
        upper_layout.addLayout(prompt_layout)
        
        # Text input area
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Enter your text here...")
        input_label = QLabel("Input Text:")
        input_label.setBuddy(self.input_text)
        
        upper_layout.addWidget(input_label)
        upper_layout.addWidget(self.input_text, 1)
        
        # Lower section with prompt text and actions
        lower_widget = QWidget()
        lower_layout = QVBoxLayout(lower_widget)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        
        # Prompt text area
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Prompt will appear here...")
        prompt_text_label = QLabel("Prompt Text:")
        prompt_text_label.setBuddy(self.prompt_text)
        
        lower_layout.addWidget(prompt_text_label)
        lower_layout.addWidget(self.prompt_text, 1)
        
        # Actions section
        actions_layout = QHBoxLayout()
        
        for shortcut, action in ACTIONS.items():
            btn = QPushButton(action)
            btn.setToolTip(f"Shortcut: {shortcut}")
            # Fix lambda binding by creating a local variable
            current_shortcut = shortcut
            btn.clicked.connect(lambda checked=False, sc=current_shortcut: self.perform_action(sc))
            actions_layout.addWidget(btn)
        
        lower_layout.addLayout(actions_layout)
        
        # Add upper and lower widgets to splitter
        splitter.addWidget(upper_widget)
        splitter.addWidget(lower_widget)
        
        # Set initial sizes
        splitter.setSizes([200, 200])
        
        # Add splitter to main layout
        layout.addWidget(splitter)
        
        # Load the first prompt automatically
        self.load_selected_prompt()
    
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
    
    def perform_action(self, shortcut):
        """Process the text based on the selected action"""
        text = self.input_text.toPlainText()
        
        if not text:
            self.status_message.emit("No text to process")
            return
            
        action = ACTIONS.get(shortcut)
        if not action:
            self.status_message.emit(f"Unknown action: {shortcut}")
            return
            
        try:
            if action == "Custom Prompt":
                prompt = self.prompt_text.toPlainText() + "\n\n"
            else:
                prompt = get_prompt(action)
                self.prompt_text.setPlainText(prompt)
                
            message = Message(
                role="user",
                content=[MessageContent(
                    type="text",
                    text=prompt + text
                )]
            )
            
            self.status_message.emit(f"Processing text with {action}...")
            new_text = ai_model.message(message).content
            self.input_text.setPlainText(new_text)
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
        
        # Keyboard shortcuts section
        shortcuts_section = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_section)
        
        shortcuts_label = QLabel("Keyboard Shortcuts")
        shortcuts_label.setFont(QFont("Arial", 12, QFont.Bold))
        shortcuts_layout.addWidget(shortcuts_label)
        
        edit_shortcuts_btn = QPushButton("Edit Shortcuts")
        edit_shortcuts_btn.clicked.connect(self.edit_shortcuts)
        shortcuts_layout.addWidget(edit_shortcuts_btn)
        
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
        layout.addWidget(shortcuts_section)
        layout.addWidget(model_section)
        layout.addStretch(1)  # Push everything to the top
    
    def edit_shortcuts(self):
        dialog = ShortcutEditor(self, ACTIONS)
        if dialog.exec_():
            # TODO: Update shortcuts based on dialog.get_shortcuts()
            pass

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
        
        # Add keyboard shortcuts
        self.setup_shortcuts()
    
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
        self.tab_widget.addTab(self.text_tab, "Text Processing")
        
        self.settings_tab = SettingsTab()
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        # Add tab widget to layout
        layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def setup_shortcuts(self):
        # Tab navigation shortcuts
        for i in range(1, min(10, self.tab_widget.count() + 1)):
            index = i - 1  # Store the index in a local variable
            shortcut = QShortcut(QKeySequence(f"Alt+{i}"), self)
            shortcut.activated.connect(lambda tab_idx=index: self.tab_widget.setCurrentIndex(tab_idx))
        
        # Action shortcuts
        for shortcut_str, action in ACTIONS.items():
            action_key = shortcut_str  # Store the shortcut string in a local variable
            shortcut = QShortcut(QKeySequence(shortcut_str), self)
            shortcut.activated.connect(lambda checked=False, key=action_key: self.text_tab.perform_action(key))
        
        # Escape to close
        escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        escape_shortcut.activated.connect(self.close)
    
    def update_status(self, message):
        """Update the status bar with a message"""
        self.status_bar.showMessage(message, 5000)  # Show for 5 seconds
        
    # Convenience properties for backward compatibility
    @property
    def input_text_area(self):
        """Backward compatibility for accessing the input text area"""
        return self.text_tab.input_text
        
    @property
    def prompt_text_area(self):
        """Backward compatibility for accessing the prompt text area"""
        return self.text_tab.prompt_text
        
    def set_input_text(self, text):
        """Set the input text content"""
        self.text_tab.input_text.setPlainText(text)
        
    def get_input_text(self):
        """Get the input text content"""
        return self.text_tab.input_text.toPlainText()
        
    def set_prompt_text(self, text):
        """Set the prompt text content"""
        self.text_tab.prompt_text.setPlainText(text)
        
    def get_prompt_text(self):
        """Get the prompt text content"""
        return self.text_tab.prompt_text.toPlainText() 