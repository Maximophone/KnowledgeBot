# keyboard_listener.py
import asyncio
import keyboard
import pyperclip
from ai import AI, get_prompt

ai_model = AI("haiku3.5")

# Define a dictionary to map actions to their corresponding functions
ACTIONS = {
    'ctrl+f1': 'correction',
    'ctrl+f2': 'light_improvement',
    'ctrl+f3': 'summarization',
    # Add more actions as needed
}

def on_hotkey():
    asyncio.run(process_clipboard_text())

async def process_clipboard_text():
    # Read text from the clipboard
    print("Processing clipboard text", flush=True)
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, pyperclip.paste)
    if not text:
        print("No text found in clipboard.", flush=True)
        return

    # Show the contextual menu and get the selected action
    action = await show_contextual_menu()

    # Perform asynchronous text processing based on the selected action
    processed_text = await async_text_processing(text, action)

    # Write the processed text back to the clipboard
    await loop.run_in_executor(None, pyperclip.copy, processed_text)
    print("Clipboard text has been processed.", flush=True)

async def async_text_processing(text, action):
    # Simulate an asynchronous operation (e.g., API call)
    prompt = get_prompt(ACTIONS[action])
    new_text = ai_model.message(prompt + text)
    return new_text

async def show_contextual_menu():
    print("Select an action:", flush=True)
    for action, description in ACTIONS.items():
        print(f"{action}: {description}")

    while True:
        for key in ACTIONS:
            if keyboard.is_pressed(key):
                return key
        await asyncio.sleep(0.1)  # Add a small delay to avoid high CPU usage

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