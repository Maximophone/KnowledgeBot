# keyboard_listener.py
import asyncio
import keyboard
import pyperclip
from ai import AI, get_prompt
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QTextEdit, QLabel, QShortcut, QComboBox
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt
from config.paths import PATHS
import os

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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.prompts = load_prompts(PATHS.prompts_library)
        self.setWindowTitle("Keyboard Listener")
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
        new_text = ai_model.message(prompt + text)
        self.input_text_area.setPlainText(new_text)
        pyperclip.copy(new_text)

def on_hotkey():
    app = QApplication([])
    window = MainWindow()
    window.input_text_area.setPlainText(pyperclip.paste())
    window.activateWindow()
    window.show()
    app.exec_()

async def main():
    print("Listening for hotkey Ctrl+`.", flush=True)
    # Register the hotkey
    keyboard.add_hotkey('ctrl+`', on_hotkey)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("Exiting...", flush=True)

if __name__ == "__main__":
    asyncio.run(main())

# # keyboard_listener.py
# import asyncio
# import keyboard
# import pyperclip
# from ai import AI, get_prompt

# ai_model = AI("haiku3.5")

# # Define a dictionary to map actions to their corresponding functions
# ACTIONS = {
#     'ctrl+f1': 'correction',
#     'ctrl+f2': 'light_improvement',
#     'ctrl+f3': 'summarization',
#     # Add more actions as needed
# }

# def on_hotkey():
#     asyncio.run(process_clipboard_text())

# async def process_clipboard_text():
#     # Read text from the clipboard
#     print("Processing clipboard text", flush=True)
#     loop = asyncio.get_event_loop()
#     text = await loop.run_in_executor(None, pyperclip.paste)
#     if not text:
#         print("No text found in clipboard.", flush=True)
#         return

#     # Show the contextual menu and get the selected action
#     action = await show_contextual_menu()

#     # Perform asynchronous text processing based on the selected action
#     processed_text = await async_text_processing(text, action)

#     # Write the processed text back to the clipboard
#     await loop.run_in_executor(None, pyperclip.copy, processed_text)
#     print("Clipboard text has been processed.", flush=True)

# async def async_text_processing(text, action):
#     # Simulate an asynchronous operation (e.g., API call)
#     prompt = get_prompt(ACTIONS[action])
#     new_text = ai_model.message(prompt + text)
#     return new_text

# async def show_contextual_menu():
#     print("Select an action:", flush=True)
#     for action, description in ACTIONS.items():
#         print(f"{action}: {description}")

#     while True:
#         for key in ACTIONS:
#             if keyboard.is_pressed(key):
#                 return key
#         await asyncio.sleep(0.1)  # Add a small delay to avoid high CPU usage

# async def main():
#     print("Listening for hotkey Ctrl+`.", flush=True)
#     # Register the hotkey
#     keyboard.add_hotkey('ctrl+`', on_hotkey)

#     try:
#         while True:
#             await asyncio.sleep(1)
#     except KeyboardInterrupt:
#         pass
#     finally:
#         print("Exiting...", flush=True)

# if __name__ == "__main__":
#     asyncio.run(main())