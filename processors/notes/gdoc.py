from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter, frontmatter_to_text
from integrations.gdoc_utils import GoogleDocUtils
import os
from prompts.prompts import get_prompt

from ai_core.types import Message, MessageContent
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class GDocProcessor(NoteProcessor):
    """Processes Google Docs by pulling their content and converting to markdown."""
    stage_name = "gdoc_synced"

    def __init__(self, input_dir: Path):
        super().__init__(input_dir)
        self.gdu = GoogleDocUtils()
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:        
        if not frontmatter:
            return False

        # Deprecated, here for backward-compatibility
        if frontmatter.get("synced"):
            return False

        if frontmatter.get("push_to_gdoc"):
            return True
        
        # Process if it has a URL
        return frontmatter.get("url")
        
    async def process_file(self, filename: str) -> None:
        """Process a Google Doc file."""
        logger.info("Processing gdoc: %s", filename)
        
        # Read the file
        content = await self.read_file(filename)
        frontmatter = parse_frontmatter(content)

        if frontmatter.get("push_to_gdoc"):
            # Get the content from the file and create a new Google Doc
            gdoc_content_md = content.split("---", 2)[2]
            folder_id = self.gdu.extract_folder_id_from_url(frontmatter["push_to_gdoc"])
            url = self.gdu.create_document_from_text(
                filename.replace(".md", ""), 
                gdoc_content_md, 
                folder_id, 
                mime_type="text/markdown")
            frontmatter["url"] = url
            frontmatter.pop("push_to_gdoc")
        else:
            # Download and process Google Doc
            gdoc_content_md = self.gdu.get_document_as_markdown(frontmatter["url"])
        
        # Update frontmatter and save
        frontmatter["synced"] = True
        final_content = frontmatter_to_text(frontmatter) + gdoc_content_md
        
        # Write back to same file
        async with aiofiles.open(self.input_dir / filename, 'w', encoding='utf-8') as f:
            await f.write(final_content)
        os.utime(self.input_dir / filename, None)

        logger.info("Processed gdoc: %s", filename)