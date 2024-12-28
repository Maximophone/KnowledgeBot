from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter, frontmatter_to_text
from gdoc_utils import GoogleDocUtils
import os
from ai import get_prompt
from ai.types import Message, MessageContent

class GDocProcessor(NoteProcessor):
    """Processes Google Docs by pulling their content and converting to markdown."""
    
    def __init__(self, input_dir: Path):
        super().__init__(input_dir)
        self.stage_name = "gdoc_synced"
        self.gdu = GoogleDocUtils()
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:        
        if not frontmatter:
            return False

        # Deprecated, here for backward-compatibility
        if frontmatter.get("synced"):
            return False
        
        # Process if it has a URL
        return frontmatter.get("url")
        
    async def process_file(self, filename: str) -> None:
        print(f"Processing gdoc: {filename}", flush=True)
        
        # Read the file
        content = await self.read_file(filename)
        frontmatter = parse_frontmatter(content)
        
        # Download and process Google Doc
        gdoc_content_html = self.gdu.get_clean_document(frontmatter["url"])
        prompt = get_prompt("summarise_gdoc")
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=prompt + gdoc_content_html
            )]
        )
        gdoc_content_md = self.ai_model.message(message).content
        
        # Update frontmatter and save
        frontmatter["synced"] = True
        final_content = frontmatter_to_text(frontmatter) + gdoc_content_md
        
        # Write back to same file
        async with aiofiles.open(self.input_dir / filename, 'w', encoding='utf-8') as f:
            await f.write(final_content)
        os.utime(self.input_dir / filename, None)

        print(f"Processed gdoc: {filename}", flush=True)