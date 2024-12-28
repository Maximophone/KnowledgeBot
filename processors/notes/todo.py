from pathlib import Path
from typing import Dict
import aiofiles
from datetime import datetime, timedelta, date
import calendar
from .base import NoteProcessor
from ..common.frontmatter import read_front_matter, parse_frontmatter
from ai.types import Message, MessageContent

class TodoProcessor(NoteProcessor):
    """Processes todo transcripts and adds them to a todo directory."""

    def __init__(self, input_dir: Path, directory_file: Path):
        super().__init__(input_dir)
        self.stage_name = "todos_extracted"
        self.required_stage = "speakers_identified"

        self.directory_file = directory_file
        self.directory_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize directory file if it doesn't exist
        if not self.directory_file.exists():
            self.directory_file.write_text("""---
tags:
  - todos
  - directory
---
# Todo Directory

""")

    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        if frontmatter.get("category") != "todo":
            return False

        # Check if file is already referenced in directory
        directory_content = self.directory_file.read_text()
        return f"[[{filename}]]" not in directory_content

    async def process_file(self, filename: str) -> None:
        print(f"Processing todos from: {filename}", flush=True)
        content = await self.read_file(filename)

        # Parse frontmatter and content
        frontmatter = parse_frontmatter(content)
        if not frontmatter:
            print(f"No frontmatter found in {filename}", flush=True)
            return

        transcript = content.split('---', 2)[2].strip()
        date_str = frontmatter.get('date', '')
        if isinstance(date_str, date):
            recording_date = date_str
        else:
            recording_date = datetime.fromisoformat(date_str) if date_str else datetime.now()
        weekday = calendar.day_name[recording_date.weekday()]

        # Extract todos using AI
        todos_prompt = self.prompt_todos + "\n\nTranscript:\n" + transcript
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=todos_prompt + transcript
            )]
        )
        todos_text = self.ai_model.message(message).content

        # Prepare the content to append
        append_content = f"\n## Todos from [[{filename}]] - {date_str}\n\n{todos_text}\n\n---\n"

        # Append to todo directory
        async with aiofiles.open(self.directory_file, "a", encoding='utf-8') as f:
            await f.write(append_content)

        print(f"Processed todos from: {filename}", flush=True)