"""
Audio Transcription and Summarization Module

This module processes audio recordings by transcribing them, extracting text,
and generating summaries. It organizes the results into predefined categories.

Key components:
- Transcription: Using AssemblyAI API
- Summarization: Using custom AI models (likely GPT-based)
- Asynchronous processing: Using asyncio and custom repeaters
"""

from typing import Dict
import yaml
import os
import whisper
import torch
import json
from ai import AI
import asyncio
from repeater import slow_repeater, start_repeaters
import traceback
import assemblyai
from mutagen import File
from datetime import datetime


# Define categories for organizing recordings
CATEGORIES = ["Meetings", "Ideas", "Unsorted"]

# File paths for different stages of processing
AUDIO_PATH = "G:\\My Drive\\Projects\\KnowledgeBot\\Audio\\{name}"
SUMMARIES_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}"
TRANSCRIPTIONS_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}\\Transcriptions"
IMPROVED_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}\\Improved"

# Sets to track files currently being processed
FILES_IN_TRANSCRIPTION = set()
FILES_IN_SUMMARIZATION = set()
FILES_IN_IMPROVEMENT = set()

# Load API keys and secrets
with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

# Initialize AI models
gemini = AI("gemini1.5")
gpt4o = AI("gpt4o")
sonnet35 = AI("sonnet3.5")
ai_model = sonnet35

# Set up AssemblyAI transcriber
assemblyai.settings.api_key = secrets["assembly_ai"]
transcriber = assemblyai.Transcriber()
config = assemblyai.TranscriptionConfig(
    speaker_labels=True,
    language_detection=True
)

def change_file_extension(filename: str, new_extension: str) -> str:
    """Change the extension of a filename."""
    return f"{os.path.splitext(filename)[0]}.{new_extension}"

def generate_summary(category: str, transcription: str) -> str:
    """Generate a summary for a given transcription based on its category."""
    with open(f"prompts/summarise_{category.lower()}.md", "r") as f:
        prompt = f.read()
    return ai_model.message(prompt + transcription)

def transcribe_audio_files(input_dir: str, output_dir: str):
    """
    Transcribe audio files from input directory and save results in output directory.
    
    This function processes each audio file, generates a transcription using AssemblyAI,
    and saves the result as both JSON and markdown files.
    """
    for filename in os.listdir(input_dir):
        json_filename = change_file_extension(filename, "json")
        md_filename = change_file_extension(filename, "md")
        
        if json_filename in os.listdir(output_dir) or filename in FILES_IN_TRANSCRIPTION:
            continue
        
        FILES_IN_TRANSCRIPTION.add(filename)
        print(f"Transcribing: {filename}", flush=True)
        
        transcript = transcriber.transcribe(f"{input_dir}/{filename}", config)
        
        # Save JSON response
        with open(f"{output_dir}/{json_filename}", "w") as f:
            json.dump(transcript.json_response, f)
        
        # Save markdown with speaker labels
        text_with_speakers = "\n".join(f"Speaker {u.speaker} : {u.text}" for u in transcript.utterances)
        with open(f"{output_dir}/{md_filename}", "w", encoding='utf-8') as f:
            f.write(text_with_speakers)
        
        print(text_with_speakers)
        FILES_IN_TRANSCRIPTION.remove(filename)

def extract_text_from_json(input_dir: str, output_dir: str):
    """
    Extract plain text from JSON transcriptions and save as markdown files.
    
    This function processes JSON files in the input directory, extracts the 'text' field,
    decodes any Unicode escape sequences, and saves the result as a markdown file.
    """
    for filename in os.listdir(input_dir):
        if filename.endswith(".md"):
            continue
        
        md_filename = change_file_extension(filename, "md")
        if md_filename in os.listdir(output_dir):
            continue
        
        print(f"Extracting text from: {filename}", flush=True)
        
        with open(f"{input_dir}/{filename}", "r", encoding='utf-8') as f:
            result = json.load(f)
        
        text = result["text"]
        decoded_text = json.loads(f'"{text}"')
        
        with open(f"{output_dir}/{md_filename}", "w", encoding='utf-8') as f:
            f.write(decoded_text)

def summarize_transcriptions(category: str, input_dir: str, output_dir: str):
    """
    Generate summaries for transcriptions in a given category.
    
    This function processes JSON transcription files, generates summaries using AI models,
    and saves the summaries as markdown files.
    """
    for filename in os.listdir(input_dir):
        if not filename.endswith(".json"):
            continue
        
        md_filename = change_file_extension(filename, "md")
        if md_filename in os.listdir(output_dir) or filename in FILES_IN_SUMMARIZATION:
            continue
        
        FILES_IN_SUMMARIZATION.add(filename)
        print(f"Summarizing: {filename}", flush=True)
        
        with open(f"{input_dir}/{filename}", "r") as f:
            result = json.load(f)
        
        summary = generate_summary(category, result["text"])
        
        with open(f"{output_dir}/{md_filename}", "w") as f:
            f.write(summary)
        
        FILES_IN_SUMMARIZATION.remove(filename)

@slow_repeater.register
async def process_all_transcriptions():
    """Transcribe all audio files across all categories."""
    for category in CATEGORIES:
        try:
            transcribe_audio_files(AUDIO_PATH.format(name=category), TRANSCRIPTIONS_PATH.format(name=category))
        except Exception:
            print(traceback.format_exc())

@slow_repeater.register
async def extract_all_transcription_text():
    """Extract text from all JSON transcriptions across all categories."""
    for category in CATEGORIES:
        try:
            extract_text_from_json(TRANSCRIPTIONS_PATH.format(name=category), 
                                   TRANSCRIPTIONS_PATH.format(name=category))
        except Exception:
            print(traceback.format_exc())

@slow_repeater.register
async def summarize_all_transcriptions():
    """Generate summaries for all transcriptions across relevant categories."""
    for category in CATEGORIES:
        if category == "Meetings":
            # Meetings are not summarized
            continue
        try:
            summarize_transcriptions(category, TRANSCRIPTIONS_PATH.format(name=category), SUMMARIES_PATH.format(name=category))
        except Exception:
            print(traceback.format_exc())

async def main():
    """Main function to start all repeaters."""
    await start_repeaters()

# Initialize Whisper model for potential use
#if torch.cuda.is_available():
#    print("Computing on GPU")
# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# model = whisper.load_model("small", device=device)

if __name__ == "__main__":
    asyncio.run(main())