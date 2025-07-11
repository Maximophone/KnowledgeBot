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
from ai_core import AI
from ai_core.types import Message, MessageContent
from config.logging_config import setup_logger
from config.paths import PATHS
from .speaker_identifier import SpeakerIdentifier

import traceback

logger = setup_logger(__name__)

class InteractionLogger(NoteProcessor):
    """
    Processes transcripts with identified speakers and adds AI-generated logs 
    to each person's note about the meeting.
    """
    stage_name = "interactions_logged"
    required_stage = SpeakerIdentifier.stage_name

    def __init__(self, input_dir: Path):
        super().__init__(input_dir)
        self.ai_model = AI("sonnet3.7")
        self.people_dir = PATHS.people_path
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        """
        Determine if a file should be processed.
        Only process files that:
        1. Have the final_speaker_mapping field in frontmatter
        2. Are categorized as "meeting" in their frontmatter
        """
        # Check if the file has the required speaker mapping
        if 'final_speaker_mapping' not in frontmatter:
            return False
            
        # Check if the file is categorized as a meeting
        category = frontmatter.get('category', '').lower()
        if category != 'meeting':
            return False
            
        return True

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
    
    async def _filter_future_logs(self, person_content: str, meeting_date_str: str) -> str:
        """
        Filters the AI Logs section in person_content, removing entries dated after meeting_date_str.
        Uses _parse_existing_logs to avoid duplicating parsing logic.
        """
        logger.debug(f"Filtering future logs for meeting date: {meeting_date_str}")
        
        # Find the AI Logs section to get the content before it
        section_exists, section_pos, content_before_section = await self._find_ai_logs_section(person_content)
        
        if not section_exists:
            logger.debug("No AI Logs section found. Returning original content.")
            return person_content
            
        # Parse the entire AI Logs section using the existing method
        all_logs_by_date = await self._parse_existing_logs(person_content)
        
        # Filter the parsed logs based on the meeting date
        filtered_logs_by_date = defaultdict(list)
        for log_date, logs in all_logs_by_date.items():
            # Compare dates as strings (YYYY-MM-DD format allows direct comparison)
            if log_date <= meeting_date_str:
                filtered_logs_by_date[log_date] = logs
            else:
                logger.debug(f"Filtering out log date {log_date} (future relative to {meeting_date_str})")

        # Reconstruct the filtered AI Logs section content
        # Need the original header structure from the content itself if possible
        ai_logs_section_content = person_content[section_pos:] # Get original section content
        header_match = re.match(r'^# AI Logs\s*(\n>\[!warning\] Do not Modify\s*\n)?\n*', ai_logs_section_content, re.IGNORECASE)
        filtered_section = header_match.group(0) if header_match else "# AI Logs\n\n" # Fallback header

        # Sort dates in descending order (newest first)
        for date in sorted(filtered_logs_by_date.keys(), reverse=True):
            filtered_section += f"## {date}\n"
            for log in filtered_logs_by_date[date]:
                filtered_section += f"*category*: {log['category']}\n"
                filtered_section += f"*source:* {log['source']}\n"
                filtered_section += f"*notes*: \n{log['notes']}\n\n"
        
        # Combine the content before the section with the filtered section
        # Ensure there's appropriate spacing
        filtered_content = content_before_section.rstrip() + "\n\n" + filtered_section.strip()
        logger.debug("Finished filtering future logs using _parse_existing_logs.")
        return filtered_content

    async def _generate_log(self, transcript_content: str, person_content: str, 
                           person_name: str, meeting_date: str, meeting_title: str) -> str:
        """Generate a log entry for a person using AI."""
        
        # Filter out future logs from the person's notes before sending to AI
        filtered_person_content = await self._filter_future_logs(person_content, meeting_date)
        
        prompt = f"""
You will be given a transcript of a meeting, the name of a participant in this meeting, and some background notes on this person. Your task is to extract specific information about this person to be appended to a markdown log. Follow these instructions carefully:

First, review the following information:

<transcript>
{transcript_content}
</transcript>

<participant_name>
{person_name}
</participant_name>

<background_notes>
{filtered_person_content} 
</background_notes>

<meeting_date>
{meeting_date}
</meeting_date>

<meeting_title>
{meeting_title}
</meeting_title>

Now, analyze the transcript and extract the following information about {person_name}:

1. New information: Identify any new information learned about this person that is not already present in the background notes. Focus on significant details that add to our understanding of the person's role, expertise, or personal characteristics.

2. Updates: Summarize the key updates or contributions this person made during the meeting. This could include project progress, challenges faced, or any other relevant information they shared.

3. Next steps: Determine the next steps or action items specifically assigned to or mentioned by this person during the meeting.

When crafting your response:
- Do not use any section headers.
- Present the information in bullet point format.
- Be concise and informative, focusing on the most relevant and important details.
- Ensure that each bullet point provides clear and specific information.
- Avoid repetition of information already present in the background notes.

Your final output should be a series of bullet points that can be directly appended to a markdown log. Include only the bullet points in your response, without any additional explanation or commentary.
        """.format(transcript_content=transcript_content, person_name=person_name, person_content=filtered_person_content, meeting_date=meeting_date, meeting_title=meeting_title)
        
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=prompt
            )]
        )
        
        return self.ai_model.message(message).content.strip()

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
        
        # Get list of speakers that have already been processed
        logged_interactions = frontmatter.get('logged_interactions', [])
        
        # Collect all speakers that need to be processed
        all_speakers = set(speaker_data.get('person_id') for speaker_data in speaker_mapping.values() 
                         if speaker_data.get('person_id'))
        
        # Filter out speakers that have already been processed
        pending_speakers = [speaker for speaker in all_speakers if speaker not in logged_interactions]
        
        if not pending_speakers:
            logger.info(f"All speakers in {filename} have already been processed")
            return
            
        logger.info(f"Processing {len(pending_speakers)} remaining speakers in {filename}")
        
        # Process each pending person
        for person_id in pending_speakers:
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
                
                # Update the person's note
                success = await self._update_person_note(
                    person_id=person_id,
                    meeting_date=meeting_date,
                    source_link=source_link,
                    log_content=log_content
                )
                
                if success:
                    # Add to logged_interactions in frontmatter
                    if 'logged_interactions' not in frontmatter:
                        frontmatter['logged_interactions'] = []
                    
                    frontmatter['logged_interactions'].append(person_id)
                    
                    # Update the transcript's frontmatter
                    file_path = self.input_dir / filename
                    updated_content = frontmatter_to_text(frontmatter) + "\n" + transcript
                    
                    # Write back to the file
                    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                        await f.write(updated_content)
                    
                    # Update file modification time
                    os.utime(file_path, None)
                    
                    logger.info(f"Updated transcript {filename} - logged interaction for {person_name}")
                else:
                    logger.error(f"Failed to update note for {person_id}")
                
            except Exception as e:
                logger.error(f"Error generating log for {person_name}: {str(e)}")
                logger.error(traceback.format_exc())
                # Continue with next person rather than failing the whole file
                continue
        
        # Check if all speakers have been processed now
        logged_interactions = frontmatter.get('logged_interactions', [])
        all_processed = all(speaker in logged_interactions for speaker in all_speakers)
        
        # Only mark the file as completely processed if all speakers have been logged
        if all_processed:
            logger.info(f"All speakers in {filename} have been processed. Marking stage as complete.")
            # The NoteProcessor._process_file will update the processing_stages in frontmatter
            # since we'll return normally
        else:
            # If not all speakers processed, raise exception to prevent stage completion
            remaining = len(all_speakers) - len(logged_interactions)
            logger.info(f"{remaining} speakers still pending in {filename}. Stage not marked complete yet.")
            raise Exception(f"Not all speakers processed in {filename}. Will retry later.")
    
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
            
            # Add/Update the log entry in the structure
            found_and_updated = False
            if meeting_date in logs_by_date:
                # Check if we already have a log for this source and update it
                for existing_log in logs_by_date[meeting_date]:
                    if existing_log['source'] == source_link:
                        logger.info(f"Overwriting existing log for {source_link} on {meeting_date} in {person_name}'s note")
                        existing_log['notes'] = log_content
                        found_and_updated = True
                        break
                
                # If not found after checking, add the new log to the existing date
                if not found_and_updated:
                    logs_by_date[meeting_date].append(new_log)
            else:
                # Create a new date entry if the date doesn't exist
                logs_by_date[meeting_date] = [new_log]
            
            # Reconstruct the AI Logs section content
            new_section = "# AI Logs\n>[!warning] Do not Modify\n\n"
            
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

    async def reset(self, filename: str) -> None:
        """
        Resets the interaction logging stage for a transcript file.
        1. Removes the logged_interactions from the transcript's frontmatter
        2. Removes the stage from processing_stages
        3. For each person in logged_interactions, removes the log entry from their person note
        """
        logger.info(f"Attempting to reset stage '{self.stage_name}' for: {filename}")
        file_path = self.input_dir / filename
        if not file_path.exists():
            logger.error(f"File not found during reset: {filename}")
            return

        try:
            # Read and parse the transcript
            content = await self.read_file(filename)
            frontmatter = parse_frontmatter(content)
            transcript = content.split('---', 2)[2].strip()

            if not frontmatter:
                logger.warning(f"No frontmatter found in {filename}. Cannot reset stage.")
                return

            processing_stages = frontmatter.get('processing_stages', [])
            if self.stage_name not in processing_stages:
                logger.info(f"Stage '{self.stage_name}' not found in processing stages for {filename}. No reset needed.")
                return

            # Get the logged interactions and meeting date
            logged_interactions = frontmatter.get('logged_interactions', [])
            meeting_date = frontmatter.get('date')
            source_link = f"[[{filename.replace('.md', '')}]]"
            
            if not meeting_date:
                logger.warning(f"Missing date in frontmatter for {filename}. Cannot identify logs to remove.")

            # For each person in logged_interactions, remove the log entry
            for person_id in logged_interactions:
                await self._remove_log_entry(person_id, meeting_date, source_link)

            # Clean the frontmatter
            if 'logged_interactions' in frontmatter:
                del frontmatter['logged_interactions']
            
            if self.stage_name in processing_stages:
                processing_stages.remove(self.stage_name)
                frontmatter['processing_stages'] = processing_stages

            # Write the updated transcript
            updated_content = frontmatter_to_text(frontmatter) + "\n" + transcript
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(updated_content)
            
            # Update modification time
            os.utime(file_path, None)
            logger.info(f"Successfully reset stage '{self.stage_name}' for: {filename}")

        except Exception as e:
            logger.error(f"Error resetting stage '{self.stage_name}' for {filename}: {e}")
            logger.error(traceback.format_exc())

    async def _remove_log_entry(self, person_id: str, meeting_date: str, source_link: str) -> None:
        """
        Removes a specific log entry from a person's note.
        Uses the existing _parse_existing_logs method to parse and manipulate logs.
        """
        # Remove [[ and ]] from person_id to get the filename
        person_name = person_id.replace('[[', '').replace(']]', '')
        person_file_path = self.people_dir / f"{person_name}.md"
        
        # Check if the person note exists
        if not person_file_path.exists():
            logger.warning(f"Person note not found during reset: {person_file_path}")
            return
        
        try:
            # Read the person's note
            async with aiofiles.open(person_file_path, 'r', encoding='utf-8') as f:
                person_content = await f.read()
            
            # Find the AI Logs section
            section_exists, section_pos, content_before_section = await self._find_ai_logs_section(person_content)
            
            if not section_exists:
                logger.warning(f"No AI Logs section found in {person_name}'s note. Nothing to reset.")
                return
                
            # Parse existing logs using the existing method
            logs_by_date = await self._parse_existing_logs(person_content)
            
            # Look for and remove the specific log entry
            entry_removed = False
            if meeting_date in logs_by_date:
                # Find and remove logs matching the source link
                logs_by_date[meeting_date] = [
                    log for log in logs_by_date[meeting_date] 
                    if log['source'] != source_link
                ]
                
                # If the date has no more logs, remove the date entry
                if not logs_by_date[meeting_date]:
                    del logs_by_date[meeting_date]
                    
                entry_removed = True
            
            # If no entry was found/removed, log and return
            if not entry_removed:
                logger.warning(f"No log entry found for {source_link} on {meeting_date} in {person_name}'s note.")
                return
                
            # Reconstruct the AI Logs section content
            new_section = "# AI Logs\n>[!warning] Do not Modify\n\n"
            
            # Sort dates in descending order (newest first)
            for date in sorted(logs_by_date.keys(), reverse=True):
                new_section += f"## {date}\n"
                for log in logs_by_date[date]:
                    new_section += f"*category*: {log['category']}\n"
                    new_section += f"*source:* {log['source']}\n"
                    new_section += f"*notes*: \n{log['notes']}\n\n"
            
            # Combine the content
            new_content = content_before_section + new_section
            
            # Write back the updated content
            async with aiofiles.open(person_file_path, 'w', encoding='utf-8') as f:
                await f.write(new_content)
            
            # Update file modification time
            os.utime(person_file_path, None)
            
            logger.info(f"Removed log entry for {meeting_date} from {person_name}'s note")
                
        except Exception as e:
            logger.error(f"Error removing log entry from {person_name}'s note: {e}")
            logger.error(traceback.format_exc())
