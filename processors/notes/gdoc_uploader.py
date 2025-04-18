from pathlib import Path
from typing import Dict
import aiofiles
import os

from .base import NoteProcessor
from ..common.frontmatter import parse_frontmatter, update_front_matter
from integrations.gdoc_utils import GoogleDocUtils
from config.logging_config import setup_logger
from .speaker_identifier import SpeakerIdentifier

logger = setup_logger(__name__)

class GDocUploadProcessor(NoteProcessor):
    """Uploads meeting transcripts to a Google Drive folder after speaker identification."""
    stage_name = "gdoc_transcript_uploaded"
    required_stage = SpeakerIdentifier.stage_name

    def __init__(self, input_dir: Path, gdrive_folder_id: str):
        super().__init__(input_dir)
        self.gdu = GoogleDocUtils()
        self.gdrive_folder_id = gdrive_folder_id

    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        # Process only if it's a meeting and hasn't been uploaded yet
        if frontmatter.get("category") != "meeting":
            return False
        if not isinstance(frontmatter.get("identified_speakers"), dict):
            return False
        if "gdoc_transcript_link" in frontmatter:
            return False
        return True

    async def process_file(self, filename: str) -> None:
        """Uploads the transcript text to Google Drive and updates the note's frontmatter."""
        logger.info(f"Uploading transcript to Google Drive for: {filename}")
        file_path = self.input_dir / filename

        # Read source transcript
        content = await self.read_file(filename)

        # Parse frontmatter and extract transcript text
        frontmatter = parse_frontmatter(content)
        if not frontmatter:
            logger.warning(f"No frontmatter found in {filename}, skipping GDoc upload.")
            return

        # Extract only the text content after the frontmatter delimiters
        try:
            transcript_text = content.split('---', 2)[2].strip()
            if not transcript_text:
                logger.warning(f"No transcript text found after frontmatter in {filename}, skipping.")
                return
        except IndexError:
            logger.warning(f"Could not split frontmatter from content in {filename}, skipping.")
            return

        # Create the Google Doc
        doc_title = filename.replace('.md', '') # Use filename (without extension) as title
        try:
            gdoc_link = self.gdu.create_document_from_text(
                title=doc_title,
                text_content=transcript_text,
                folder_id=self.gdrive_folder_id
            )
        except Exception as e:
            logger.error(f"Failed to create Google Doc for {filename}: {e}")
            raise # Re-raise to prevent marking stage as complete

        if not gdoc_link:
            logger.error(f"Failed to get Google Doc link after creation for {filename}.")
            raise Exception(f"Google Doc creation returned no link for {filename}")

        # Update frontmatter of the original transcript note
        try:
            frontmatter['gdoc_transcript_link'] = gdoc_link
            update_front_matter(file_path, frontmatter)
            os.utime(file_path, None) # Update modification time
            logger.info(f"Successfully uploaded transcript and updated frontmatter for: {filename}")
        except Exception as e:
            logger.error(f"Failed to update frontmatter for {filename} after GDoc upload: {e}")
            # Consider how to handle this - the GDoc exists but the link isn't saved.
            # For now, re-raise to signal an issue.
            raise 