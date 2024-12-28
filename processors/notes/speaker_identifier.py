from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import read_front_matter, parse_frontmatter, frontmatter_to_text
from ai import AI
from ai.types import Message, MessageContent
import os

class SpeakerIdentifier(NoteProcessor):
    """Identifies speakers in transcripts using AI."""
    
    def __init__(self, input_dir: Path):
        super().__init__(input_dir)
        self.ai_model = AI("sonnet3.5")
        self.tiny_model = AI("haiku")
        self.required_stage = "classified"
        self.stage_name = "speakers_identified"
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        return True
                 
    async def identify_speaker(self, transcript: str, speaker_label: str) -> str:
        """Use AI to identify a specific speaker from the transcript."""
        prompt = f"""Based on this conversation transcript, who is Speaker {speaker_label}? 
        Analyze their speaking patterns, knowledge, and role in the conversation.
        If you can confidently identify them, return just their first name.
        If you cannot confidently identify them, return "unknown".
        
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
        print(f"Identifying speakers in: {filename}", flush=True)
        content = await self.read_file(filename)
        
        # Parse frontmatter and content
        frontmatter = parse_frontmatter(content)
        transcript = content.split('---', 2)[2].strip()
        
        # Find all unique speakers
        speaker_lines = [line for line in transcript.split('\n') if line.startswith('Speaker ')]
        unique_speakers = set(line.split(':')[0].strip() for line in speaker_lines)
        
        # Identify each speaker
        speaker_mapping = {}
        for speaker in unique_speakers:
            print(f"Identifying {speaker}...", flush=True)
            label = speaker.replace('Speaker ', '')
            identified_name_verbose = await self.identify_speaker(transcript, label)
            identified_name = self.consolidate_answer(identified_name_verbose)

            print(f"Result : {identified_name_verbose}", flush=True)
            if identified_name.lower() != "unknown":
                speaker_mapping[speaker] = identified_name
        
        # Replace identified speakers in the transcript
        new_transcript = transcript
        for speaker, name in speaker_mapping.items():
            new_transcript = new_transcript.replace(f"{speaker}:", f"{name}:")
        
        # Update frontmatter to mark identified speakers
        identified_speakers = frontmatter.get('identified_speakers', [])
        if identified_speakers is None:
            identified_speakers = []
        identified_speakers.extend(speaker_mapping.values())
        frontmatter['identified_speakers'] = identified_speakers
        
        # Save updated file
        full_content = frontmatter_to_text(frontmatter) + "\n" + new_transcript
        async with aiofiles.open(self.input_dir / filename, "w", encoding='utf-8') as f:
            await f.write(full_content)
        os.utime(self.input_dir / filename, None)

        print(f"Completed speaker identification for: {filename}", flush=True)

    def identify_speakers(self, text: str) -> str:
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=self.prompt_identify + text
            )]
        )
        return self.ai_model.message(message).content.strip()

    def identify_speakers_tiny(self, text: str) -> str:
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=self.prompt_identify_tiny + text
            )]
        )
        return self.tiny_model.message(message).content.strip()