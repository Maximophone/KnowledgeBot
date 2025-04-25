from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter, update_front_matter
from config.logging_config import setup_logger
from .speaker_identifier import SpeakerIdentifier
import os
import aiofiles.os

logger = setup_logger(__name__)


class MeetingProcessor(NoteProcessor):
    """Creates structured meeting notes from meeting transcripts."""
    
    stage_name = "meeting_note_created"
    required_stage = SpeakerIdentifier.stage_name

    def __init__(self, input_dir: Path, output_dir: Path, template_path: Path):
        super().__init__(input_dir)
        
        self.output_dir = output_dir
        self.template_path = template_path
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        return False # Deactivated for now
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

    async def reset(self, filename: str) -> None:
        """
        Resets the meeting note stage for a file.
        If the corresponding output note exists and is identical to the template
        (after placeholder replacements), it deletes the output note.
        """
        logger.info(f"Attempting to reset stage '{self.stage_name}' for: {filename}")
        output_path = self.output_dir / filename
        input_path = self.input_dir / filename # Path to the source transcript

        # 1. Check and read input file first
        if not input_path.exists():
            logger.error(f"Source file {input_path} not found. Cannot reset stage '{self.stage_name}'.")
            return

        try:
            async with aiofiles.open(input_path, 'r', encoding='utf-8') as f:
                source_content = await f.read()
            frontmatter = parse_frontmatter(source_content)

            if not frontmatter:
                logger.warning(f"No frontmatter found in source file {input_path}. Cannot reset stage '{self.stage_name}'.")
                return

            processing_stages = frontmatter.get('processing_stages', [])
            if self.stage_name not in processing_stages:
                logger.info(f"Stage '{self.stage_name}' not found in processing stages for {filename}. No reset needed.")
                # Optional: Check if output file exists anyway and delete if it matches template?
                # For now, if stage isn't marked, assume reset isn't required.
                return

            # 2. Handle the output file (delete if it exists and matches processed template)
            deleted_output = False
            if output_path.exists():
                try:
                    # Read the raw template content
                    async with aiofiles.open(self.template_path, 'r', encoding='utf-8') as f:
                        template_content = await f.read()
                        
                    # Perform the same replacements as process_file
                    date = frontmatter.get('date', '')
                    if hasattr(date, 'strftime'):
                        date = date.strftime('%Y-%m-%d')
                    title = filename
                    
                    processed_template_content = template_content.replace("{{date}}", date)
                    processed_template_content = processed_template_content.replace("{{title}}", title)

                    # Read the existing output file content
                    async with aiofiles.open(output_path, 'r', encoding='utf-8') as f:
                        output_content = await f.read()

                    # Compare processed template with output content
                    if processed_template_content == output_content:
                        logger.info(f"Output file {output_path} matches the processed template. Deleting.")
                        await aiofiles.os.remove(output_path)
                        deleted_output = True
                        logger.info(f"Successfully deleted {output_path}.")
                    else:
                        logger.info(f"Output file {output_path} content differs from the processed template. No action taken on file.")
                except FileNotFoundError:
                    logger.error(f"Template file {self.template_path} not found during reset for {filename}. Cannot compare/delete output file.")
                except Exception as e:
                    logger.error(f"Error during output file comparison/deletion for {filename}: {e}", exc_info=True)
            else:
                logger.info(f"Output file {output_path} does not exist. No file deletion needed.")

            # 3. Update frontmatter of the input file
            logger.info(f"Removing stage '{self.stage_name}' from frontmatter of {filename}.")
            frontmatter['processing_stages'].remove(self.stage_name)
            
            # Use the synchronous update_front_matter, following pattern from other resets
            update_front_matter(input_path, frontmatter) 
            os.utime(input_path, None) # Update modification time
            
            logger.info(f"Successfully reset stage '{self.stage_name}' for: {filename}")

        except Exception as e:
            logger.error(f"Error resetting stage '{self.stage_name}' for {filename}: {e}", exc_info=True)