import asyncio
import keyboard
import pyperclip
from ai import AI, get_prompt

ai_model = AI("haiku3.5")

def on_hotkey():
    asyncio.run(process_clipboard_text())

async def process_clipboard_text():
    # Read text from the clipboard
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, pyperclip.paste)
    if not text:
        print("No text found in clipboard.")
        return

    # Perform asynchronous text processing
    processed_text = await async_text_processing(text)

    # Write the processed text back to the clipboard
    await loop.run_in_executor(None, pyperclip.copy, processed_text)
    print("Clipboard text has been processed.")

async def async_text_processing(text):
    # Simulate an asynchronous operation (e.g., API call)
    prompt = get_prompt("correction")
    new_text = ai_model.message(prompt + text)
    return new_text

async def main():
    print("Listening for hotkey Ctrl+Shift+E. Press Ctrl+Shift+Q to exit.")
    # Register the hotkey
    keyboard.add_hotkey('ctrl+shift+e', on_hotkey)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("Exiting...")

if __name__ == "__main__":
    main()
