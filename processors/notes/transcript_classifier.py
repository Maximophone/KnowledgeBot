from pathlib import Path
from typing import Dict
import aiofiles
from .base import NoteProcessor
from ..common.frontmatter import read_front_matter, update_front_matter
from ai import AI, get_prompt
from ai.types import Message, MessageContent
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class TranscriptClassifier(NoteProcessor):
    """Classifies transcripts using AI based on content."""
    stage_name = "classified"
    required_stage = "transcribed" # Assuming transcription is needed first

    def __init__(self, input_dir: Path):
        super().__init__(input_dir)
        self.ai_model = AI("haiku3.5")  # Using smaller model for classification
        self.prompt_classify = get_prompt("classify_transcript")
        self.prompt = get_prompt("transcript_classifier")
        
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
        """Process a transcript file."""
        logger.info("Classifying transcript: %s", filename)
        
        # Read file content
        content = await self.read_file(filename)
        
        # Get text after frontmatter
        text = content.split('---', 2)[2].strip()
        
        # Classify the transcript
        category = self.classify(text)
        logger.info("Classified as: %s", category)
        
        # Update frontmatter
        file_path = self.input_dir / filename
        frontmatter = read_front_matter(file_path)
        frontmatter["category"] = category
        if "tags" not in frontmatter:
            frontmatter["tags"] = []
        frontmatter["tags"].append(category)
        
        update_front_matter(file_path, frontmatter)
        logger.info("Updated classification for: %s", filename)