from pathlib import Path
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter
from ..common.markdown import create_wikilink


class IdeaProcessor(NoteProcessor):
    """Processes idea transcripts and adds them to an idea directory."""
    
    def __init__(self, input_dir: Path, directory_file: Path):
        super().__init__(input_dir)
        self.stage_name = "ideas_extracted"
        self.required_stage = "speakers_identified"

        self.directory_file = directory_file
        self.directory_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize directory file if it doesn't exist
        if not self.directory_file.exists():
            self.directory_file.write_text("""---
tags:
  - ideas
  - directory
---
# Ideas Directory

""")
        
    def should_process(self, filename: str) -> bool:
        if "- idea -" not in filename.lower():
            return False
            
        # Check if file is already referenced in directory
        directory_content = self.directory_file.read_text()
        return f"[[{filename}]]" not in directory_content
        
    async def process_file(self, filename: str) -> None:
        print(f"Processing ideas from: {filename}", flush=True)
        content = await self.read_file(filename)
        
        # Parse frontmatter and content
        frontmatter = parse_frontmatter(content)
        if not frontmatter:
            print(f"No frontmatter found in {filename}", flush=True)
            return
            
        transcript = content.split('---', 2)[2].strip()
        
        # Extract ideas using AI
        ideas_prompt = """Analyze this transcript and extract ALL distinct ideas, even if some are only briefly mentioned.
            
            Important guidelines:
            - Only split into multiple ideas if the transcript clearly discusses completely different, unrelated topics
            - Most transcripts should result in just one idea
            - For each idea, provide:
                1. A specific, searchable title (3-7 words)
                2. A concise summary that captures the essence in 1-2 short sentences
            
            Format your response as:
            ### {Title}
            {Concise summary focusing on the core concept, written in clear, direct language}
            
            Example format:
            ### Spaced Repetition for Habit Formation
            Using spaced repetition algorithms to optimize habit trigger timing, adapting intervals based on adherence data.
            
            ### Personal Knowledge Graph with Emergence
            A note-taking system where connections between notes evolve automatically based on semantic similarity and usage patterns.
            
            Transcript:
            """
        
        ideas_text = self.ai_model.message(ideas_prompt + transcript)
        
        # Prepare the content to append
        date_str = frontmatter.get('date', '')
        append_content = f"\n## Ideas from [[{filename}]] - {date_str}\n\n{ideas_text}\n\n---\n"
        
        # Append to ideas directory
        async with aiofiles.open(self.directory_file, "a", encoding='utf-8') as f:
            await f.write(append_content)
            
        print(f"Processed ideas from: {filename}", flush=True)