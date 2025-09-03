from pathlib import Path
from typing import Dict
import aiofiles
import os
import traceback

from .base import NoteProcessor
from ..common.frontmatter import read_text_from_content, read_text_from_file, parse_frontmatter_from_content, set_frontmatter_in_file, frontmatter_to_text
from integrations.notion_integration import NotionClient
from config.logging_config import setup_logger
from .speaker_identifier import SpeakerIdentifier

logger = setup_logger(__name__)

class NotionUploadProcessor(NoteProcessor):
    """Uploads meeting transcripts to a Notion database after speaker identification."""
    stage_name = "notion_transcript_uploaded"
    required_stage = SpeakerIdentifier.stage_name

    def __init__(self, input_dir: Path, database_url: str):
        super().__init__(input_dir)
        self.notion = NotionClient()
        self.database_url = database_url

    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        # Process only if it's a meeting and hasn't been uploaded yet
        if "noupload" in frontmatter.get("source_tags", []):
            return False
        if frontmatter.get("category") != "meeting":
            return False
        if not isinstance(frontmatter.get("final_speaker_mapping"), dict):
            return False
        if len(frontmatter.get("final_speaker_mapping", {})) <= 1:
            # We need at least two speakers to upload
            return False
        if "notion_transcript_url" in frontmatter or "notion_page_id" in frontmatter:
            return False
        return True

    async def process_file(self, filename: str) -> None:
        """Uploads the transcript to Notion and updates the note's frontmatter."""
        logger.info(f"Uploading transcript to Notion for: {filename}")
        file_path = self.input_dir / filename

        # Read source transcript
        content = await self.read_file(filename)

        # Parse frontmatter and extract transcript text
        frontmatter = parse_frontmatter_from_content(content)
        if not frontmatter:
            logger.warning(f"No frontmatter found in {filename}, skipping Notion upload.")
            return

        # Ensure we have a meeting date for the Notion Date property
        meeting_date = frontmatter.get("date")
        if not meeting_date:
            logger.warning(f"No 'date' found in frontmatter for {filename}, skipping Notion upload.")
            return

        # Extract only the text content after the frontmatter delimiters
        try:
            transcript_text = read_text_from_file(file_path)
            if not transcript_text:
                logger.warning(f"No transcript text found after frontmatter in {filename}, skipping.")
                return
        except IndexError:
            logger.warning(f"Could not split frontmatter from content in {filename}, skipping.")
            return

        # Build markdown to upload: include a YAML frontmatter with the Notion Date property
        # Notion property names are case-sensitive; use "Date" for the database property
        # Also ensure no single line exceeds Notion's paragraph rich_text limit by splitting long lines
        safe_transcript_text = self._split_long_lines(transcript_text, max_len=1900)
        upload_frontmatter = {"ntn:date:Date": {"start": meeting_date}}
        upload_md = frontmatter_to_text(upload_frontmatter) + safe_transcript_text

        # Set title and parent type (database)
        page_title = filename.replace('.md', '')
        parent_type = "database" if "?v=" in self.database_url else "page"

        try:
            page_response = self.notion.create_page_from_markdown(
                markdown_content=upload_md,
                parent_url=self.database_url,
                title=page_title,
                parent_type=parent_type
            )
        except Exception as e:
            logger.error(f"Failed to create Notion page for {filename}: {e}")
            raise

        # Extract page identifiers
        notion_url = None
        notion_id = None
        if isinstance(page_response, dict):
            notion_url = page_response.get("url")
            notion_id = page_response.get("id")
        elif isinstance(page_response, str):
            if page_response.startswith("http"):
                notion_url = page_response
            else:
                notion_id = page_response

        # Update frontmatter of the original transcript note
        try:
            if notion_url:
                frontmatter['notion_transcript_url'] = notion_url
            if notion_id:
                frontmatter['notion_page_id'] = notion_id
            set_frontmatter_in_file(file_path, frontmatter)
            os.utime(file_path, None) # Update modification time
            logger.info(f"Successfully uploaded transcript to Notion and updated frontmatter for: {filename}")
        except Exception as e:
            logger.error(f"Failed to update frontmatter for {filename} after Notion upload: {e}")
            raise

    def _split_long_lines(self, text: str, max_len: int = 1900) -> str:
        """Split any single line longer than max_len, preferring sentence boundaries.

        The downstream Markdown→Notion converter creates one paragraph per line, so
        we must ensure no line exceeds Notion's ~2000 char per-paragraph limit.

        Strategy per line:
        - If length <= max_len, keep as-is
        - Else cut within the window [0:max_len], preferring the last '.', '!' or '?' near the end
        - Fallback to last space; otherwise hard cut at max_len
        """
        output_lines = []
        for line in text.split("\n"):
            remaining = line
            while len(remaining) > max_len:
                window = remaining[:max_len]
                # Prefer sentence-ending punctuation
                last_punct = -1
                for punct in ('.', '!', '?', '…'):
                    idx = window.rfind(punct)
                    if idx > last_punct:
                        last_punct = idx
                # Use punctuation cut if reasonably late in the window
                threshold = int(max_len * 0.6)
                if last_punct >= threshold:
                    split_idx = last_punct + 1  # include the punctuation
                else:
                    # Try last space
                    space_idx = window.rfind(' ')
                    if space_idx >= threshold:
                        split_idx = space_idx
                    else:
                        split_idx = max_len
                segment = remaining[:split_idx].rstrip()
                output_lines.append(segment)
                remaining = remaining[split_idx:].lstrip()
            output_lines.append(remaining)
        return "\n".join(output_lines)

    async def reset(self, filename: str) -> None:
        """
        Resets the Notion upload stage for a transcript file.
        1. Removes Notion references from the transcript's frontmatter.
        2. Removes the stage from processing_stages.
        Note: Deleting the Notion page is not supported by this integration.
        """
        logger.info(f"Attempting to reset stage '{self.stage_name}' for: {filename}")
        file_path = self.input_dir / filename
        if not file_path.exists():
            logger.error(f"File not found during reset: {filename}")
            return

        try:
            # Read and parse the transcript
            content = await self.read_file(filename)
            frontmatter = parse_frontmatter_from_content(content)

            if not frontmatter:
                logger.warning(f"No frontmatter found in {filename}. Cannot reset stage.")
                return

            processing_stages = frontmatter.get('processing_stages', [])

            # Clean the frontmatter
            frontmatter.pop('notion_transcript_url', None)
            frontmatter.pop('notion_page_id', None)
            if self.stage_name in processing_stages:
                processing_stages.remove(self.stage_name)
                frontmatter['processing_stages'] = processing_stages

            # Write the updated transcript
            updated_content = set_frontmatter_in_file(file_path, frontmatter)

            # Update modification time
            os.utime(file_path, None)
            logger.info(f"Successfully reset stage '{self.stage_name}' for: {filename}")

        except Exception as e:
            logger.error(f"Error resetting stage '{self.stage_name}' for {filename}: {e}")
            logger.error(traceback.format_exc())