from pathlib import Path
import json
import asyncio
import aiofiles
import assemblyai
from typing import Set, Dict
from datetime import datetime

from .utils import get_recording_date
from ..common.frontmatter import frontmatter_to_text

from ai import AI, get_prompt
from ai.types import Message, MessageContent
import re
import os
import asyncio

class AudioTranscriber:
    """Handles the transcription of audio files to markdown and JSON."""
    
    def __init__(
        self, 
        input_dir: Path,
        output_dir: Path,
        processed_dir: Path,
        api_key: str
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.processed_dir = processed_dir
        self.files_in_process: Set[str] = set()
        
        # Set up AssemblyAI
        assemblyai.settings.api_key = api_key
        self.transcriber = assemblyai.Transcriber()
        self.config = assemblyai.TranscriptionConfig(
            speaker_labels=True,
            language_detection=True,
            word_boost=["Pause IA", "Pause AI", "Moiri"],
        )
        
        # Create necessary directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        # Add small AI model for title generation
        self.ai_model = AI("haiku3.5")
        self.prompt_title = get_prompt("transcript_title")

    def generate_title(self, text: str) -> str:
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=self.prompt_title + text
            )]
        )
        return self.ai_model.message(message).content
        
    async def transcribe_audio_file(self, file_path: Path) -> assemblyai.Transcript:
        """Transcribe a single audio file using AssemblyAI."""
        # TODO: Make this properly async when AssemblyAI supports it
        transcript = self.transcriber.transcribe(str(file_path), self.config)
        return transcript
    
    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        _, ext = os.path.splitext(filename)
        return ext.lower() not in ['.mkv', '.mp4', '.avi']
    
    async def process_single_file(self, filename: str) -> None:
        """Process a single audio file: transcribe and save outputs."""
        file_path = self.input_dir / filename
        
        try:
            # Get recording date
            recording_date = get_recording_date(file_path)
            date_str = recording_date.strftime("%Y-%m-%d")
            
            # Transcribe
            transcript = await self.transcribe_audio_file(file_path)
            
            # Process speaker labels with LeMUR
            text_with_speaker_labels = "\n".join(
                f"Speaker {utt.speaker}:\n{utt.text}\n" 
                for utt in transcript.utterances
            )
            
            title = None
            # Check if original filename starts with date pattern
            filename_without_ext = file_path.stem
            if filename_without_ext.startswith(date_str):
                # Extract everything after the date as title
                title_parts = filename_without_ext[len(date_str):].strip()
                if title_parts.startswith("-"):
                    title = title_parts[1:].strip()
            
            if title is None:
                # Generate new title if none found in filename
                title = self.generate_title(transcript.text)

            print(f"Title: {title}", flush=True)
            
            # Create safe filename base
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            base_filename = f"{date_str}-{safe_title}"
            
            # Save JSON response
            json_filename = f"{base_filename}.json"
            json_path = self.output_dir / json_filename
            async with aiofiles.open(json_path, "w") as f:
                await f.write(json.dumps(transcript.json_response, indent=2))
            
            print(f"Saved JSON: {json_filename}", flush=True)

            new_filename = date_str + "_" + filename

            # Prepare frontmatter
            frontmatter = {
                "tags": ["transcription"],
                "date": date_str,
                "original_file": new_filename,
                "title": title,
                "json_data": json_filename,
                "AutoNoteMover": "disable",
                "processing_stages": ["transcribed"]  # Initialize as list
            }
            
            full_content = frontmatter_to_text(frontmatter) + "\n" + text_with_speaker_labels

            md_filename = f"{base_filename}.md"
            md_path = self.output_dir / md_filename

            async with aiofiles.open(md_path, "w", encoding='utf-8') as f:
                await f.write(full_content)
            
            print(f"Saved MD: {md_filename}", flush=True)

            # Move original file to processed folder
            file_path.rename(self.processed_dir / new_filename)
            
            print(f"Processed: {filename} -> {md_filename}", flush=True)
            
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}", flush=True)
            raise
        finally:
            self.files_in_process.remove(filename)

    async def process_all(self) -> None:
        """Process all audio files in the input directory."""
        tasks = []
        for file_path in self.input_dir.iterdir():
            await asyncio.sleep(0)
            filename = file_path.name
            if not self.should_process(filename, None):
                continue
            # Skip if already being processed
            if filename in self.files_in_process:
                continue
            self.files_in_process.add(filename)
            print(f"Queuing transcription: {filename}", flush=True)
            task = asyncio.create_task(self.process_single_file(filename))
            tasks.append(task)
        if tasks:
            await asyncio.gather(*tasks)