from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter, frontmatter_to_text
from ai import AI, get_prompt

class IdeaCleanupProcessor(NoteProcessor):
    """Processes idea transcripts into clean, well-formatted entries."""
    
    def __init__(self, input_dir: Path, output_dir: Path):
        super().__init__(input_dir)
        self.stage_name = "idea_cleaned"
        self.required_stage = "classified"
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_format = get_prompt("idea_format")
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        if frontmatter.get("category") != "idea":
            return False
            
        # Check if cleaned idea note already exists
        output_path = self.output_dir / filename
        return not output_path.exists()
        
    async def process_file(self, filename: str) -> None:
        print(f"Cleaning up idea: {filename}", flush=True)
        
        # Read source transcript
        content = await self.read_file(filename)
        
        # Parse frontmatter and content
        frontmatter = parse_frontmatter(content)
        if not frontmatter:
            print(f"No frontmatter found in {filename}", flush=True)
            return
            
        transcript = content.split('---', 2)[2].strip()
        
        # Generate formatted idea entry
        formatted_entry = self.ai_model.message(
            self.prompt_format + "\n\nEntry:\n" + transcript
        ).content
        
        # Create new frontmatter
        new_frontmatter = {
            "title": frontmatter.get("title", ""),
            "date": frontmatter.get("date", ""),
            "tags": ["idea"],
            "original_transcript": f"[[Transcriptions/{filename}]]",
            "category": "idea",
            "processing_stages": frontmatter.get("processing_stages", []) + ["idea_cleaned"]
        }
        
        # Combine into final content
        final_content = (
            frontmatter_to_text(new_frontmatter) +
            "\n# Idea Development\n\n" +
            formatted_entry +
            "\n\n## Original Transcription\n" +
            transcript
        )
        
        # Save to output directory
        output_path = self.output_dir / filename
        async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
            await f.write(final_content)
            
        print(f"Cleaned up idea: {filename}", flush=True)