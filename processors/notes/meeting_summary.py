from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import read_front_matter
from ai_core.types import Message, MessageContent
from config.logging_config import setup_logger
from prompts.prompts import get_prompt

from .meeting import MeetingProcessor

logger = setup_logger(__name__)


class MeetingSummaryProcessor(NoteProcessor):
    """Adds AI-generated summaries to meeting notes based on transcripts."""
    
    stage_name = "meeting_summary_generated"
    required_stage = MeetingProcessor.stage_name

    def __init__(self, input_dir: Path, transcript_dir: Path):
        super().__init__(input_dir)
        self.transcript_dir = transcript_dir
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:            
        # Check if transcript exists and get its frontmatter            
        transcript_path = self.transcript_dir / filename
        if not transcript_path.exists():
            return False

        transcript_frontmatter = read_front_matter(transcript_path)
        if "speakers_identified" not in transcript_frontmatter.get("processing_stages", []):
            return False

        return True
        
    async def process_file(self, filename: str) -> None:
        """Generate a meeting summary."""
        logger.info("Generating meeting summary for: %s", filename)
        
        # Read meeting note
        note_content = await self.read_file(filename)
        
        # Extract pre-meeting and meeting notes sections
        pre_meeting_notes = ""
        meeting_notes = ""
        
        # Find Pre-Meeting Notes section
        if "# Pre-Meeting Notes" in note_content:
            pre_meeting_parts = note_content.split("# Pre-Meeting Notes", 1)
            if len(pre_meeting_parts) > 1:
                next_section = pre_meeting_parts[1].find("\n# ")
                if next_section != -1:
                    pre_meeting_notes = pre_meeting_parts[1][:next_section].strip()
                else:
                    pre_meeting_notes = pre_meeting_parts[1].strip()
        
        # Find Meeting Notes section
        if "# Meeting Notes" in note_content:
            meeting_parts = note_content.split("# Meeting Notes", 1)
            if len(meeting_parts) > 1:
                next_section = meeting_parts[1].find("\n# ")
                if next_section != -1:
                    meeting_notes = meeting_parts[1][:next_section].strip()
                else:
                    meeting_notes = meeting_parts[1].strip()
        
        # Prepare context
        context = ""
        if pre_meeting_notes:
            context += f"""Pre-Meeting Notes:
{pre_meeting_notes}

"""
        if meeting_notes:
            context += f"""Meeting Notes:
{meeting_notes}

"""

        # Get transcript content
        transcript_path = self.transcript_dir / filename
        transcript_content = transcript_path.read_text()
        
        # Generate summary points
        summary_prompt = f"""Analyze this meeting transcript and create a clear, concise summary.
        Format your response as bullet points covering the key discussions and decisions.
        Focus on the most important points and ensure the summary is actionable and clear.
        No need to list action items, this will be analysed by another AI.
        Make use of markdown formatting. Don't use headers larger than "####".
        
        {context}
        Transcript:
        """
        
        summary_message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=summary_prompt + transcript_content
            )]
        )
        summary = self.ai_model.message(summary_message).content
        
        # Generate next steps
        next_steps_prompt = f"""Review this meeting transcript and extract all action items and next steps.
        For each action item:
        - Identify who is responsible
        - What needs to be done
        - Any mentioned deadlines or timeframes
        
        Format as bullet points grouped by person.
        If no clear owner is specified for an action, list it under "Team".
        Make use of markdown formatting. Don't use headers larger than "####".
        
        {context}
        Transcript:
        """
        
        next_steps_message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=next_steps_prompt + transcript_content
            )]
        )
        next_steps = self.ai_model.message(next_steps_message).content
        
        # Prepare new summary section
        new_summary = f"""## Executive Summary

### Key Points
{summary}

### Next Steps
{next_steps}
"""
        
        # Replace existing summary section
        parts = note_content.split('## Executive Summary')
        if len(parts) != 2:
            logger.warning("Could not find Executive Summary section in %s", filename)
            return
            
        # Find the end of the summary section (next heading or end of file)
        rest = parts[1]
        next_section_match = rest.find('\n## ')
        if next_section_match != -1:
            new_content = parts[0] + new_summary + rest[next_section_match:]
        else:
            new_content = parts[0] + new_summary
            
        # Save updated content
        async with aiofiles.open(self.input_dir / filename, 'w', encoding='utf-8') as f:
            await f.write(new_content)
            
        logger.info("Added summary to meeting note: %s", filename)