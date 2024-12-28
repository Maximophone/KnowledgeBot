from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import read_front_matter, update_front_matter
from ai import AI, get_prompt
from ai.types import Message, MessageContent

class TranscriptClassifier(NoteProcessor):
    """Classifies transcripts using AI."""
    
    def __init__(self, input_dir: Path):
        super().__init__(input_dir)
        self.ai_model = AI("haiku3.5")  # Using smaller model for classification
        self.prompt_classify = get_prompt("classify_transcript")
        self.required_stage = "transcribed"
        self.stage_name = "classified"
        
    def should_process(self, filename: str, frontmatter: Dict) -> bool:
        # Process if it's a transcription and hasn't been classified
        return "transcription" in frontmatter.get("tags", [])
        
    def classify(self, text: str) -> str:
        message = Message(
            role="user",
            content=[MessageContent(
                type="text",
                text=self.prompt_classify + text
            )]
        )
        return self.ai_model.message(message).content
        
    async def process_file(self, filename: str) -> None:
        print(f"Classifying transcript: {filename}", flush=True)
        
        # Read file content
        content = await self.read_file(filename)
        
        # Get text after frontmatter
        text = content.split('---', 2)[2].strip()
        
        # Classify the transcript
        category = self.classify(text)
        print(f"Classified as: {category}", flush=True)
        
        # Update frontmatter
        file_path = self.input_dir / filename
        frontmatter = read_front_matter(file_path)
        frontmatter["category"] = category
        if "tags" not in frontmatter:
            frontmatter["tags"] = []
        frontmatter["tags"].append(category)
        
        update_front_matter(file_path, frontmatter)
        print(f"Updated classification for: {filename}", flush=True)