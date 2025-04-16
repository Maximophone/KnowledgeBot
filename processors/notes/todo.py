from pathlib import Path
from typing import Dict
import aiofiles
from datetime import datetime, timedelta, date
import calendar
from .base import NoteProcessor
from ..common.frontmatter import read_front_matter, parse_frontmatter
from ai.types import Message, MessageContent
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class TodoProcessor(NoteProcessor):
    """Processes todo transcripts and adds them to a todo directory."""
    stage_name = "todos_extracted"
    required_stage = "speakers_identified"

    def __init__(self, input_dir: Path, directory_file: Path):
        super().__init__(input_dir)

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
        self.prompt_todos = """
Analyze this transcript and extract ALL distinct todo items, even if some are only briefly mentioned.
Important guidelines:
- For each todo item, provide:
    1. A concise description of the task
    2. The due date, if explicitly stated or if it can be inferred from the context (e.g., "in 3 days", "by Monday")
- If no due date is mentioned or can be inferred, leave the due date blank
- Format each todo item as follows:
    - [ ] {{Task description}} 📅 {{Due date}}
- Use the "Tasks" plugin formatting for Obsidian
- IMPORTANT: All due dates MUST be in YYYY-MM-DD format
- Convert all relative dates (like "tomorrow", "next week", "in 3 days") to absolute dates based on the recording date
- **The recording date for this transcript is {recording_date_str} ({weekday})**
Format your response as a list of todo items, nothing else.
Example format:
- [ ] Finish coding the todo processor 📅 2023-06-15
- [ ] Test the todo processor
- [ ] Deploy the todo processor to production 📅 2024-09-20
Transcript:
        """

    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        if frontmatter.get("category") != "todo":
            return False

        # Check if file is already referenced in directory
        directory_content = self.directory_file.read_text()
        return f"[[{filename}]]" not in directory_content

    async def process_file(self, filename: str) -> None:
        """Process todos from a note."""
        logger.info("Processing todos from: %s", filename)
        
        content = await self.read_file(filename)

        # Parse frontmatter and content
        frontmatter = parse_frontmatter(content)
        
        if not frontmatter:
            logger.warning("No frontmatter found in %s", filename)
            return

        transcript = content.split('---', 2)[2].strip()
        date_str = frontmatter.get('date', '')
        if isinstance(date_str, date):
            recording_date = date_str
        else:
            recording_date = datetime.fromisoformat(date_str) if date_str else datetime.now()
        recording_date_str = recording_date.strftime('%Y-%m-%d')
        weekday = calendar.day_name[recording_date.weekday()]

        # Extract todos using AI
        todos_prompt = self.prompt_todos.format(recording_date_str=recording_date_str, weekday=weekday) + "\n\nTranscript:\n" + transcript
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

        logger.info("Processed todos from: %s", filename)