from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter, frontmatter_to_text
from ai import get_prompt

class ConversationProcessor(NoteProcessor):
    """Processes conversation notes and reformats them with AI-generated summaries."""
    
    def __init__(self, input_dir: Path):
        super().__init__(input_dir)
        self.stage_name = "conversation_processed"
        self.prompt_format = get_prompt("conversation_format")
        self.prompt_summary = get_prompt("conversation_summary")
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        return True
        
    async def process_file(self, filename: str) -> None:
        print(f"Processing conversation: {filename}", flush=True)
        
        # Read source file
        content = await self.read_file(filename)
        
        # Parse frontmatter if it exists
        has_frontmatter = content.startswith('---')
        if has_frontmatter:
            frontmatter = parse_frontmatter(content)
            text = content.split('---', 2)[2].strip()
        else:
            frontmatter = {
                'processing_stages': []
            }
            text = content.strip()
        
        # Format the conversation using AI
        formatted_conversation = self.ai_model.message(
            self.prompt_format + "\n\nTranscript:\n" + text
        ).content
        
        # Generate summary
        summary = self.ai_model.message(
            self.prompt_summary + "\n\nTranscript:\n" + text
        ).content
        
        # Update frontmatter
        frontmatter['tags'] = frontmatter.get('tags', [])
        if "conversation" not in frontmatter["tags"]:
            frontmatter['tags'].append("conversation")

        # Combine into final content
        final_content = (
            frontmatter_to_text(frontmatter) +
            "\n## Summary\n" +
            summary + "\n\n" +
            "## Conversation\n" +
            formatted_conversation
        )
        
        # Save back to same file
        async with aiofiles.open(self.input_dir / filename, 'w', encoding='utf-8') as f:
            await f.write(final_content)
            
        print(f"Processed conversation: {filename}", flush=True)