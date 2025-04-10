from pathlib import Path
from typing import Dict, Any, List, Tuple
import aiofiles
import os
import re
import datetime
import logging
from collections import defaultdict

from .base import NoteProcessor
from ..common.frontmatter import read_front_matter, parse_frontmatter, frontmatter_to_text
from ai import AI
from ai.types import Message, MessageContent
from config.logging_config import setup_logger
from config.paths import PATHS

logger = setup_logger(__name__)

class InteractionLogger(NoteProcessor):
    """
    Processes transcripts with identified speakers and adds AI-generated logs 
    to each person's note about the meeting.
    """
    
    def __init__(self, input_dir: Path):
        super().__init__(input_dir)
        self.ai_model = AI("sonnet3.7")
        self.required_stage = "speakers_identified"
        self.stage_name = "interactions_logged"
        self.people_dir = PATHS.people_path
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        """
        Determine if a file should be processed.
        Only process files that have the final_speaker_mapping field in frontmatter.
        """
        return 'final_speaker_mapping' in frontmatter

    async def _find_ai_logs_section(self, content: str) -> Tuple[bool, int, str]:
        """
        Find the AI Logs section in a note.
        Returns (exists, position, content_before_section)
        """
        # Look for the level 1 heading
        match = re.search(r'^# AI Logs\s*$', content, re.MULTILINE)
        
        if not match:
            # Section doesn't exist
            return False, len(content), content
        
        # Section exists, return its position
        return True, match.start(), content[:match.start()]
    
    async def _parse_existing_logs(self, content: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parse existing AI logs into a structured format.
        Returns a dict with dates as keys and lists of log entries as values.
        """
        # Find the AI Logs section first
        section_exists, section_pos, _ = await self._find_ai_logs_section(content)
        
        if not section_exists:
            return {}
            
        # Extract the AI Logs section content
        section_content = content[section_pos:]
        
        # Parse the logs by date
        logs_by_date = defaultdict(list)
        
        # Regular expression to find date headers (## YYYY-MM-DD)
        date_headers_iter = re.finditer(r'^## (\d{4}-\d{2}-\d{2})\s*$', section_content, re.MULTILINE)
        
        # Convert iterator to list to safely get next items and allow len()
        date_headers = list(date_headers_iter)
        
        for i, date_match in enumerate(date_headers):
            date_str = date_match.group(1)
            start_pos = date_match.end()
            
            # Find the end of this date section (next date header or end of content)
            end_pos = date_headers[i+1].start() if i < len(date_headers) - 1 else len(section_content)
            
            date_section = section_content[start_pos:end_pos].strip()
            
            # Parse individual log entries in this date section
            entry_matches = re.finditer(r'\*category\*: (.*?)\n\*source:\* (.*?)\n\*notes\*:\s(.*?)(?=\n\*category\*:|$)', 
                                       date_section, re.DOTALL)
            
            for entry_match in entry_matches:
                category = entry_match.group(1).strip()
                source = entry_match.group(2).strip()
                notes = entry_match.group(3).strip()
                
                logs_by_date[date_str].append({
                    'category': category,
                    'source': source,
                    'notes': notes
                })
        
        return logs_by_date
    
    async def _generate_log(self, transcript_content: str, person_content: str, 
                           person_name: str, meeting_date: str, meeting_title: str) -> str:
        """Generate a log entry for a person using AI."""
        prompt = f"""You are analyzing a meeting transcript to create a concise log entry that will be saved in the personal note for {person_name}.

MEETING INFORMATION:
Date: {meeting_date}
Title: {meeting_title}

YOUR TASK:
Review the meeting transcript and create a brief summary specifically for {person_name}'s records.
Focus on:
1. Key updates or information this person shared during the meeting
2. Any action items or next steps assigned to or mentioned by this person
3. Any important information that was directed to this person

FORMATTING REQUIREMENTS:
- DO NOT use any Markdown headings (# or ## or ### etc)
- Use bullet points (- or *) or plain paragraphs only
- DO NOT include any introductions, explanations, or metadata
- Keep it concise but informative, aim for 2-4 bullet points unless extensive content exists

PERSON'S CURRENT NOTE:
{person_content}

MEETING TRANSCRIPT:
{transcript_content}

Write ONLY the log content in plain text with bullet points. No headings of any kind.
"""
        
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=prompt
            )]
        )
        
        return self.ai_model.message(message).content.strip()

    async def _update_person_note(self, person_id: str, 
                                 meeting_date: str, 
                                 source_link: str, 
                                 log_content: str) -> bool:
        """
        Update a person's note with the new log entry.
        Returns True if successful, False otherwise.
        """
        # Remove [[ and ]] from person_id to get the filename
        person_name = person_id.replace('[[', '').replace(']]', '')
        person_file_path = self.people_dir / f"{person_name}.md"
        
        # Check if the person note exists
        if not person_file_path.exists():
            logger.warning(f"Person note not found: {person_file_path}")
            return False
        
        try:
            # Read the person's note
            async with aiofiles.open(person_file_path, 'r', encoding='utf-8') as f:
                person_content = await f.read()
            
            # Parse existing logs
            logs_by_date = await self._parse_existing_logs(person_content)
            
            # Find or create the AI Logs section
            section_exists, section_pos, content_before_section = await self._find_ai_logs_section(person_content)
            
            # Create the new log entry
            new_log = {
                'category': 'meeting',
                'source': source_link,
                'notes': log_content
            }
            
            # Add to the logs by date structure
            if meeting_date in logs_by_date:
                # Check if we already have a log for this source
                for existing_log in logs_by_date[meeting_date]:
                    if existing_log['source'] == source_link:
                        logger.info(f"Log for {source_link} already exists in {person_name}'s note")
                        return True
                
                # Add the new log to the existing date
                logs_by_date[meeting_date].append(new_log)
            else:
                # Create a new date entry
                logs_by_date[meeting_date] = [new_log]
            
            # Reconstruct the AI Logs section content
            new_section = "# AI Logs\n>[!warning] Do not Modify\n\n"
            
            # Add the warning callout if we're creating the section for the first time
            if not section_exists:
                new_section += ">[!warning] Do not Modify\n\n"
            
            # Sort dates in descending order (newest first)
            for date in sorted(logs_by_date.keys(), reverse=True):
                new_section += f"## {date}\n"
                for log in logs_by_date[date]:
                    new_section += f"*category*: {log['category']}\n"
                    new_section += f"*source:* {log['source']}\n"
                    new_section += f"*notes*: \n{log['notes']}\n\n"
            
            # Combine the content
            if section_exists:
                new_content = content_before_section + new_section
            else:
                new_content = person_content + "\n\n" + new_section
            
            # Write back the updated content
            async with aiofiles.open(person_file_path, 'w', encoding='utf-8') as f:
                await f.write(new_content)
            
            # Update file modification time
            os.utime(person_file_path, None)
            
            logger.info(f"Updated {person_name}'s note with log for {meeting_date}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating person note {person_name}: {str(e)}")
            return False
    
    async def process_file(self, filename: str) -> None:
        """Process identified speakers in a transcript and add logs to their notes."""
        logger.info(f"Processing interactions from transcript: {filename}")
        
        # Read the transcript file
        content = await self.read_file(filename)
        frontmatter = parse_frontmatter(content)
        transcript = content.split('---', 2)[2].strip()
        
        # Extract required information
        meeting_date = frontmatter.get('date')
        meeting_title = frontmatter.get('title', filename)
        source_link = f"[[{filename.replace('.md', '')}]]"
        
        if not meeting_date:
            logger.error(f"Missing date in frontmatter for {filename}")
            raise ValueError(f"Meeting date is required in frontmatter for {filename}")
        
        # Get the speaker mapping
        speaker_mapping = frontmatter.get('final_speaker_mapping', {})
        
        if not speaker_mapping:
            logger.warning(f"Empty speaker mapping in {filename}")
            return
        
        # Track updates to apply atomically
        person_updates = []
        
        # Process each identified person
        for speaker_id, speaker_data in speaker_mapping.items():
            # Get the person ID (with Obsidian link format)
            person_id = speaker_data.get('person_id')
            
            if not person_id:
                logger.warning(f"Missing person_id for speaker {speaker_id} in {filename}")
                continue
            
            # Get the person's name (for use in the prompt)
            person_name = person_id.replace('[[', '').replace(']]', '')
            
            # Read the person's note for context
            person_file_path = self.people_dir / f"{person_name}.md"
            
            if not person_file_path.exists():
                logger.warning(f"Person note not found: {person_file_path}")
                continue
            
            try:
                # Read the person's note
                async with aiofiles.open(person_file_path, 'r', encoding='utf-8') as f:
                    person_content = await f.read()
                
                # Generate the log entry
                log_content = await self._generate_log(
                    transcript_content=transcript,
                    person_content=person_content,
                    person_name=person_name,
                    meeting_date=meeting_date,
                    meeting_title=meeting_title
                )
                
                # Store the update to apply later
                person_updates.append((person_id, meeting_date, source_link, log_content))
                
            except Exception as e:
                logger.error(f"Error generating log for {person_name}: {str(e)}")
                raise
        
        # Apply all updates atomically (all or nothing)
        for person_id, meeting_date, source_link, log_content in person_updates:
            success = await self._update_person_note(
                person_id=person_id,
                meeting_date=meeting_date,
                source_link=source_link,
                log_content=log_content
            )
            
            if not success:
                raise Exception(f"Failed to update note for {person_id}")
        
        logger.info(f"Successfully processed interactions for {filename}")
