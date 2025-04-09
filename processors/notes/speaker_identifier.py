from pathlib import Path
from typing import Dict, Any
import aiofiles
import aiohttp
import json
import os
import re

from .base import NoteProcessor
from ..common.frontmatter import read_front_matter, parse_frontmatter, frontmatter_to_text
from ai import AI
from ai.types import Message, MessageContent
from config.logging_config import setup_logger
from config.user_config import TARGET_DISCORD_USER_ID, USER_NAME, USER_ORGANIZATION
from config.services_config import SPEAKER_MATCHER_UI_URL
from integrations.discord import DiscordIOCore

logger = setup_logger(__name__)

class SpeakerIdentificationError(Exception):
    """Exception raised when speaker identification processing encounters an error."""
    pass

class ResultsNotReadyError(Exception):
    """Exception raised when the speaker matching results are not yet available.
    This is expected behavior and will cause the processor to retry later."""
    pass

class SpeakerIdentifier(NoteProcessor):
    """Identifies speakers in transcripts using AI, initiates matching UI, and processes results."""
    
    def __init__(self, input_dir: Path, discord_io: DiscordIOCore):
        super().__init__(input_dir)
        self.ai_model = AI("sonnet3.7")
        self.tiny_model = AI("haiku")
        self.required_stage = "classified"
        self.stage_name = "speakers_identified"
        self.discord_io = discord_io
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        """
        Determine if the file should be processed.
        The base class already checks if the stage_name exists in processing_stages.
        We provide additional criteria here.
        """
        return True

    def _extract_unique_speakers(self, transcript: str) -> set:
        """Extract all unique speaker labels from the transcript."""
        speaker_lines = [line for line in transcript.split('\n') if line.startswith('Speaker ')]
        return set(line.split(':')[0].strip() for line in speaker_lines)
                 
    async def identify_speaker(self, transcript: str, speaker_label: str) -> str:
        """Use AI to identify a specific speaker from the transcript."""
        prompt = f"""Based on this conversation transcript, who is Speaker {speaker_label}? 
        Analyze their speaking patterns, knowledge, and role in the conversation.
        
        Output your analysis first, then just their first name, or "unknown" if you cannot confidently identify them.

        Transcript:
        {transcript}"""
        
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=prompt
            )]
        )
        return self.ai_model.message(message).content.strip()

    def consolidate_answer(self, text: str) -> str:
        """Extract just the name from the verbose AI response."""
        prompt = f"""The text below is the answer from an LLM that was tasked to identify someone.
        Please return only the first name of the person identified, or "unknown" if the LLM was unable to identify the person. 
        Your answer must not include anything else, only this one word.

        Text:
        {text}
        """
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=prompt
            )]
        )
        return self.tiny_model.message(message).content.strip()
        
    async def process_file(self, filename: str) -> None:
        """Process a transcript file through all substages: identify speakers, initiate matching, and process results."""
        logger.info("Processing file for speaker identification: %s", filename)
        
        content = await self.read_file(filename)
        frontmatter = parse_frontmatter(content)
        transcript = content.split('---', 2)[2].strip()
        
        # --- Special case: Check for single speaker transcripts ---
        unique_speakers = self._extract_unique_speakers(transcript)
        if len(unique_speakers) == 1:
            await self._handle_single_speaker(filename, frontmatter, transcript, list(unique_speakers)[0])
            return
        
        # --- Substage 1: Speaker Identification (if not already done) ---
        if 'identified_speakers' not in frontmatter:
            await self._substage1_identify_speakers(filename, frontmatter, transcript)
            # Reload frontmatter and transcript after modifications
            content = await self.read_file(filename)
            frontmatter = parse_frontmatter(content)
            transcript = content.split('---', 2)[2].strip()
        else:
            logger.info("Speakers already identified for: %s", filename)
        
        # --- Substage 2: Initiate Matching UI & Send Discord Notification (if needed) ---
        if 'speaker_matcher_task_id' not in frontmatter:
            await self._substage2_initiate_matching(filename, frontmatter, transcript)
            # Reload frontmatter and transcript after modifications
            content = await self.read_file(filename)
            frontmatter = parse_frontmatter(content)
            transcript = content.split('---', 2)[2].strip()
        else:
            logger.info("Speaker matching UI already initiated for: %s", filename)
        
        # --- Substage 3: Poll for Results & Process Them (if needed) ---
        if 'final_speaker_mapping' not in frontmatter:
            await self._substage3_process_results(filename, frontmatter, transcript)
        else:
            logger.info("Speaker matching results already processed for: %s", filename)

    async def _handle_single_speaker(self, filename: str, frontmatter: Dict, transcript: str, speaker_label: str) -> None:
        """Handle transcripts with a single speaker by automatically assigning user's info."""
        logger.info("Detected single speaker transcript in %s. Automatically assigning to user: %s", filename, USER_NAME)
        
        # Create a final speaker mapping for a single speaker
        final_mapping = {
            speaker_label: {
                "name": USER_NAME,
                "organisation": f"[[{USER_ORGANIZATION}]]",
                "person_id": f"[[{USER_NAME}]]"
            }
        }
        
        # Add to frontmatter
        frontmatter['final_speaker_mapping'] = final_mapping
        
        # Replace speaker labels in the transcript
        new_transcript = transcript
        pattern = re.escape(f"{speaker_label}:") 
        new_transcript = re.sub(pattern, f"{USER_NAME} ([[{USER_ORGANIZATION}]]):", new_transcript)
        
        # Save the updated file
        full_content = frontmatter_to_text(frontmatter) + "\n" + new_transcript
        async with aiofiles.open(self.input_dir / filename, "w", encoding='utf-8') as f:
            await f.write(full_content)
        os.utime(self.input_dir / filename, None)
        
        logger.info("Completed automatic speaker identification for single-speaker file: %s", filename)
            
    async def _substage1_identify_speakers(self, filename: str, frontmatter: Dict, transcript: str) -> None:
        """Substage 1: Identify speakers using AI and save to frontmatter."""
        logger.info("Identifying speakers in: %s", filename)
        unique_speakers = self._extract_unique_speakers(transcript)
        
        speaker_mapping = {}
        for speaker in unique_speakers:
            logger.info("Identifying %s...", speaker)
            label = speaker.replace('Speaker ', '')
            identified_name_verbose = await self.identify_speaker(transcript, label)
            identified_name = self.consolidate_answer(identified_name_verbose)

            logger.info("Result: %s", identified_name_verbose)
            # Store both name and reason
            speaker_mapping[speaker] = {
                "name": identified_name,
                "reason": identified_name_verbose.strip()
            }
        
        # Save the identified speakers to frontmatter immediately
        frontmatter['identified_speakers'] = speaker_mapping
        temp_content = frontmatter_to_text(frontmatter) + "\n" + transcript
        async with aiofiles.open(self.input_dir / filename, "w", encoding='utf-8') as f:
            await f.write(temp_content)
        os.utime(self.input_dir / filename, None)
        logger.info("Saved identified speakers to frontmatter for: %s", filename)
    
    async def _substage2_initiate_matching(self, filename: str, frontmatter: Dict, transcript: str) -> None:
        """Substage 2: Initiate matching UI service and send Discord notification."""
        speaker_mapping = frontmatter.get('identified_speakers', {})
        
        # Prepare payload for UI service
        speakers_payload = []
        for speaker_id, data in speaker_mapping.items():
            speaker_info = {
                "speaker_id": speaker_id,
                "description": data.get("reason", "No description available.")
            }
            # Only include extracted_name if it's not "unknown"
            if data.get("name") and data["name"].lower() != "unknown":
                speaker_info["extracted_name"] = data["name"]
            speakers_payload.append(speaker_info)
        
        meeting_id = filename
        meeting_context = f"Transcript from meeting: {filename}"
        payload = {
            "meeting_id": meeting_id,
            "meeting_context": meeting_context,
            "speakers": speakers_payload
        }
        
        # Call UI service
        try:
            logger.info("Calling speaker matcher UI service for: %s", filename)
            async with aiohttp.ClientSession() as session:
                async with session.post(SPEAKER_MATCHER_UI_URL, json=payload) as response:
                    response.raise_for_status()
                    response_data = await response.json()
                    
                    ui_url = response_data.get("ui_url")
                    results_url = response_data.get("results_url")
                    task_id = response_data.get("task_id")
                    
                    if not (ui_url and results_url and task_id):
                        error_msg = f"Incomplete response from UI service: {response_data}"
                        logger.error(error_msg)
                        raise SpeakerIdentificationError(error_msg)
                        
                    logger.info("Successfully called UI service for: %s", filename)
        except (aiohttp.ClientError, json.JSONDecodeError) as e:
            error_msg = f"Error calling UI service: {str(e)}"
            logger.error(error_msg)
            raise SpeakerIdentificationError(error_msg) from e
        
        # Send Discord notification
        try:
            logger.info("Sending Discord notification for: %s", filename)
            dm_text = f"Please help identify speakers for the meeting '{meeting_id}'.\n" \
                      f"Click here to start: {ui_url}"
            success = await self.discord_io.send_dm(TARGET_DISCORD_USER_ID, dm_text)
            
            if not success:
                error_msg = f"Failed to send Discord DM for: {filename}"
                logger.error(error_msg)
                raise SpeakerIdentificationError(error_msg)
                
            logger.info("Successfully sent Discord notification for: %s", filename)
        except Exception as e:
            error_msg = f"Error sending Discord notification: {str(e)}"
            logger.error(error_msg)
            raise SpeakerIdentificationError(error_msg) from e
        
        # Both API call and Discord notification succeeded, update frontmatter
        frontmatter['speaker_matcher_ui_url'] = ui_url
        frontmatter['speaker_matcher_results_url'] = results_url
        frontmatter['speaker_matcher_task_id'] = task_id
        
        # Save updated file
        full_content = frontmatter_to_text(frontmatter) + "\n" + transcript
        async with aiofiles.open(self.input_dir / filename, "w", encoding='utf-8') as f:
            await f.write(full_content)
        os.utime(self.input_dir / filename, None)
        logger.info("Completed speaker matching UI initiation for: %s", filename)
    
    async def _substage3_process_results(self, filename: str, frontmatter: Dict, transcript: str) -> None:
        """Substage 3: Poll for matching results and process when ready."""
        # Get the results URL from the frontmatter
        results_url = frontmatter.get('speaker_matcher_results_url')
        if not results_url:
            error_msg = f"Missing results URL in frontmatter for: {filename}"
            logger.error(error_msg)
            raise SpeakerIdentificationError(error_msg)
        
        # Poll the results endpoint
        logger.info("Polling for speaker matching results for: %s", filename)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(results_url) as response:
                    response.raise_for_status()
                    response_data = await response.json()
                    
                    # Check if results are ready
                    status = response_data.get("status")
                    
                    if status == "PENDING":
                        logger.info("Results not ready yet for: %s. Will retry later.", filename)
                        # This is expected behavior that will result in retry
                        raise ResultsNotReadyError(f"Results not ready for task: {response_data.get('task_id')}")
                    
                    if status != "COMPLETE":
                        error_msg = f"Unexpected status from results endpoint: {status}"
                        logger.error(error_msg)
                        raise SpeakerIdentificationError(error_msg)
                    
                    # Extract the final speaker mapping
                    results = response_data.get("results", {})
                    if not results:
                        error_msg = f"Empty results received for: {filename}"
                        logger.error(error_msg)
                        raise SpeakerIdentificationError(error_msg)
                    
                    logger.info("Successfully received matching results for: %s", filename)
                    logger.info("Speaker mapping from UI: %s", results)
        except ResultsNotReadyError:
            # Re-raise this exception to trigger retry
            raise
        except (aiohttp.ClientError, json.JSONDecodeError) as e:
            error_msg = f"Error polling results endpoint: {str(e)}"
            logger.error(error_msg)
            raise SpeakerIdentificationError(error_msg) from e
        
        # Process the results: create a modified copy for frontmatter with Obsidian links
        frontmatter_results = {}
        for speaker_id, speaker_data in results.items():
            # Create a deep copy of the speaker data
            frontmatter_speaker_data = dict(speaker_data)
            
            # Wrap person_id and organisation with [[ ]] for Obsidian links in frontmatter
            if 'person_id' in frontmatter_speaker_data:
                frontmatter_speaker_data['person_id'] = f"[[{frontmatter_speaker_data['person_id']}]]"
            
            if 'organisation' in frontmatter_speaker_data:
                frontmatter_speaker_data['organisation'] = f"[[{frontmatter_speaker_data['organisation']}]]"
            
            frontmatter_results[speaker_id] = frontmatter_speaker_data
        
        # Update frontmatter with the modified results (containing Obsidian links)
        frontmatter['final_speaker_mapping'] = frontmatter_results
        
        # Replace speaker labels in the transcript with the identified names
        # (using the original results without [[ ]] for replacements)
        new_transcript = transcript
        for speaker_id, speaker_data in results.items():
            # Get the person's name and organization
            name = speaker_data.get("name", "Unknown")
            organization = speaker_data.get("organisation", "")
            
            # Create a replacement string
            if organization:
                replacement = f"{name} ({organization}):"
            else:
                replacement = f"{name}:"
            
            # Replace all occurrences of the speaker ID with the name
            pattern = re.escape(f"{speaker_id}:") # Escape special characters in the speaker ID
            new_transcript = re.sub(pattern, replacement, new_transcript)
        
        # Save the updated file
        full_content = frontmatter_to_text(frontmatter) + "\n" + new_transcript
        async with aiofiles.open(self.input_dir / filename, "w", encoding='utf-8') as f:
            await f.write(full_content)
        os.utime(self.input_dir / filename, None)
        logger.info("Completed speaker identification workflow for: %s", filename)
    
    def identify_speakers(self, text: str) -> str:
        prompt = self.prompt_identify + text
        return self.ai_model.message(prompt).content.strip()

    def identify_speakers_tiny(self, text: str) -> str:
        prompt = self.prompt_identify_tiny + text
        return self.tiny_model.message(prompt).content.strip()