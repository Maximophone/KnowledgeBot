from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QTextEdit, QLabel, QShortcut, QComboBox, QApplication
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt
import os
import pyperclip
from ai import AI, get_prompt
from ai.types import Message, MessageContent
from config.paths import PATHS
import sys

ai_model = AI("haiku3.5")

# Define a dictionary to map actions to their corresponding functions
ACTIONS = {
    'a': 'correction',
    's': 'light_improvement',
    'd': 'conversation_format',
    'q': 'Custom Prompt',
    'w': 'Load Prompt',
    # Add more actions as needed
}

def load_prompts(directory):
    prompts = {}
    for filename in os.listdir(directory):
        if filename.endswith('.md'):
            with open(os.path.join(directory, filename), 'r') as file:
                title = filename.split(".md")[0]
                prompts[title] = filename
    return prompts

class PopupWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Add these window flags to make the window stay on top
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        self.prompts = load_prompts(PATHS.prompts_library)
        self.setWindowTitle("Text Processor")
        self.setGeometry(100, 100, 600, 400)

        # Create a central widget and layout
        central_widget = QWidget()
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Add prompt dropdown
        self.prompt_dropdown = QComboBox()
        self.prompt_dropdown.addItems(self.prompts.keys())
        layout.addWidget(self.prompt_dropdown)

        # Add action buttons
        for shortcut, description in ACTIONS.items():
            button = QPushButton(description + " (" + shortcut + ")")
            button.clicked.connect(lambda checked, action=shortcut: self.perform_action(action))
            layout.addWidget(button)

            # Add keyboard shortcut
            qt_shortcut = QShortcut(QKeySequence(shortcut), self)
            qt_shortcut.activated.connect(lambda action=shortcut: self.perform_action(action))

        # Add text areas
        self.input_text_area = QTextEdit()
        self.input_text_area.setPlaceholderText("Input text goes here...")
        layout.addWidget(QLabel("Text"))
        layout.addWidget(self.input_text_area)

        self.prompt_text_area = QTextEdit()
        layout.addWidget(QLabel("Prompt Text"))
        layout.addWidget(self.prompt_text_area)

        escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        escape_shortcut.activated.connect(self.close)

    def perform_action(self, action):
        text = self.input_text_area.toPlainText()
        prompt_file = self.prompts[self.prompt_dropdown.currentText()]
        if ACTIONS[action] == "Custom Prompt":
            prompt = self.prompt_text_area.toPlainText() + "\n\n"
        elif ACTIONS[action] == "Load Prompt":
            with open(os.path.join(PATHS.prompts_library, prompt_file)) as f:
                prompt = f.read()
            self.prompt_text_area.setPlainText(prompt)
            return
        else:
            prompt = get_prompt(ACTIONS[action])
            self.prompt_text_area.setPlainText(prompt)
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=prompt + text
            )]
        )
        new_text = ai_model.message(message).content
        self.input_text_area.setPlainText(new_text)
        pyperclip.copy(new_text) 