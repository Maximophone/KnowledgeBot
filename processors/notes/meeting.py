from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter
from config.logging_config import setup_logger

logger = setup_logger(__name__)


class MeetingProcessor(NoteProcessor):
    """Creates structured meeting notes from meeting transcripts."""
    
    stage_name = "meeting_note_created"
    required_stage = "speakers_identified"

    def __init__(self, input_dir: Path, output_dir: Path, template_path: Path):
        super().__init__(input_dir)
        
        self.output_dir = output_dir
        self.template_path = template_path
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        if frontmatter.get("category") != "meeting":
            return False
            
        # Check if meeting note already exists
        output_path = self.output_dir / filename
        return not output_path.exists()
        
    async def process_file(self, filename: str) -> None:
        """Process a meeting note."""
        logger.info("Creating meeting note for: %s", filename)
        
        # Read source transcript
        content = await self.read_file(filename)
        frontmatter = parse_frontmatter(content)
        
        if not frontmatter:
            logger.warning("No frontmatter found in %s", filename)
            return
            
        # Read template
        async with aiofiles.open(self.template_path, 'r', encoding='utf-8') as f:
            template = await f.read()
            
        # Extract key information
        date = frontmatter.get('date', '')
        if hasattr(date, 'strftime'):  # Check if it's a date object
            date = date.strftime('%Y-%m-%d')
        
        # Replace template placeholders
        template = template.replace("{{date}}", date)
        template = template.replace("{{title}}", filename)
        
        # Save to output directory
        output_path = self.output_dir / filename
        async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
            await f.write(template)
            
        logger.info("Created meeting note: %s", filename)