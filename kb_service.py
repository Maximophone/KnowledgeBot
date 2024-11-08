import asyncio
from obsidian_ai import process_file, needs_answer, VAULT_PATH
from file_watcher import start_file_watcher
from transcribe import (
    start_repeaters
)

async def run_obsidian_ai():
    await start_file_watcher(VAULT_PATH, process_file, needs_answer, use_polling=True)

async def run_transcribe_services():
    await start_repeaters()

async def main():
    obsidian_ai_task = asyncio.create_task(run_obsidian_ai())
    transcribe_task = asyncio.create_task(run_transcribe_services())

    await asyncio.gather(obsidian_ai_task, transcribe_task)

if __name__ == "__main__":
    asyncio.run(main())