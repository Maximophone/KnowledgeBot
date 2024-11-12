from pathlib import Path
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter, frontmatter_to_text
from ..common.markdown import sanitize_filename
from ai import get_prompt

class MeditationProcessor(NoteProcessor):
    """Processes meditation transcripts into structured notes."""
    
    def __init__(self, input_dir: Path, output_dir: Path):
        super().__init__(input_dir)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.meditation_prompt = get_prompt("process_meditation")
        
    def should_process(self, filename: str) -> bool:
        if not filename.endswith('.md'):
            return False
        if "- meditation -" not in filename.lower():
            return False
        # Check if output file exists
        return not (self.output_dir / filename).exists()
        
    async def process_file(self, filename: str) -> None:
        print(f"Processing meditation: {filename}", flush=True)
        content = await self.read_file(filename)
        
        # Parse frontmatter and content
        frontmatter = parse_frontmatter(content)
        if not frontmatter:
            print(f"No frontmatter found in {filename}", flush=True)
            return
            
        transcript = content.split('---', 2)[2].strip()
        
        # Generate meditation content using AI        
        ai_response = self.ai_model.message(self.meditation_prompt + transcript)
        
        # Create audio link
        original_file = frontmatter.get('original_file', '')
        sanitized_filename = original_file.replace(" ", "%20")
        audio_link = f"G:/My Drive/KnowledgeBot/Audio/Processed/{sanitized_filename}"
        
        # Create new frontmatter
        new_frontmatter = {
            "title": frontmatter.get("title", ""),
            "date": frontmatter.get("date", ""),
            "tags": ["meditation"],
            "original_transcript": f"[[{filename}]]",
            "audio_file": audio_link,
            "category": "meditation"
        }
        
        # Combine into final markdown
        final_content = (
            frontmatter_to_text(new_frontmatter) +
            "\n" +
            ai_response +
            "\n\n## Original Transcription\n" +
            transcript
        )
        
        # Save to output directory
        output_path = self.output_dir / filename
        async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
            await f.write(final_content)
            
        print(f"Saved meditation note: {filename}", flush=True)