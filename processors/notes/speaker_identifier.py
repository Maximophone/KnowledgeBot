from pathlib import Path
from typing import Dict
import aiofiles
import aiohttp
import json
import os

from .base import NoteProcessor
from ..common.frontmatter import read_front_matter, parse_frontmatter, frontmatter_to_text
from ai import AI
from ai.types import Message, MessageContent
from config.logging_config import setup_logger
from config.user_config import TARGET_DISCORD_USER_ID
from config.services_config import SPEAKER_MATCHER_UI_URL
from integrations.discord import DiscordIOCore

logger = setup_logger(__name__)

class SpeakerIdentificationError(Exception):
    """Exception raised when speaker identification processing encounters an error."""
    pass

class SpeakerIdentifier(NoteProcessor):
    """Identifies speakers in transcripts using AI and initiates matching UI."""
    
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
        """Process a transcript file to identify speakers and initiate matching UI."""
        logger.info("Processing file for speaker identification: %s", filename)
        
        content = await self.read_file(filename)
        frontmatter = parse_frontmatter(content)
        transcript = content.split('---', 2)[2].strip()
        
        # --- Step 1: Speaker Identification (if not already done) ---
        speaker_mapping = frontmatter.get('identified_speakers', {})
        
        if not speaker_mapping:
            logger.info("Identifying speakers in: %s", filename)
            speaker_lines = [line for line in transcript.split('\n') if line.startswith('Speaker ')]
            unique_speakers = set(line.split(':')[0].strip() for line in speaker_lines)
            
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
        else:
            logger.info("Speakers already identified for: %s", filename)
        
        # --- Step 2: If task_id doesn't exist, contact UI service and send Discord notification ---
        if 'speaker_matcher_task_id' in frontmatter:
            logger.info("Speaker matching UI already initiated for: %s", filename)
            return
            
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
        logger.info("Completed speaker identification workflow for: %s", filename)

    def identify_speakers(self, text: str) -> str:
        prompt = self.prompt_identify + text
        return self.ai_model.message(prompt).content.strip()

    def identify_speakers_tiny(self, text: str) -> str:
        prompt = self.prompt_identify_tiny + text
        return self.tiny_model.message(prompt).content.strip()