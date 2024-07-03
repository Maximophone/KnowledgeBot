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

from gdoc_utils import GoogleDocUtils


# Define categories for organizing recordings
CATEGORIES = ["Meetings", "Ideas", "Unsorted"]

VAULT_PATH = "G:\\My Drive\\Obsidian"
MARKDOWNLOAD_PATH = f"{VAULT_PATH}\\MarkDownload"
GDOC_PATH = f"{VAULT_PATH}\\gdoc"
SOURCES_PATH = f"{VAULT_PATH}\\Source"
SOURCE_TEMPLATE_PATH = f"{VAULT_PATH}\\Templates\\source.md"

# File paths for different stages of processing
AUDIO_PATH = "G:\\My Drive\\Projects\\KnowledgeBot\\Audio\\{name}"
SUMMARIES_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}"
TRANSCRIPTIONS_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}\\Transcriptions"
IMPROVED_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}\\Improved"

TRANSCR_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\Transcriptions"
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

GDU = GoogleDocUtils()

def parse_frontmatter(txt: str) -> Dict:
    """Returns None if it cannot be parsed"""
    pieces = txt.split("---")
    if len(pieces) < 3:
        return None
    frontmatter_txt = pieces[1]
    try:
        frontmatter = yaml.safe_load(frontmatter_txt)
    except yaml.YAMLError:
        return None
    return frontmatter

def frontmatter_to_text(frontmatter: Dict) -> str:
    """"""
    text = yaml.dump(frontmatter)
    return "---\n" + text + "\n---\n"

def write_gdoc(text: str, filename: str, frontmatter: Dict):
    """Overwrites a gdoc file with the text pulled from the google doc"""
    final_text = frontmatter_to_text(frontmatter) + text
    file_path = f"{GDOC_PATH}\\{filename}"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_text)
    os.utime(file_path, None)

def write_md_summary(summary: str, filename: str, new_filename: str, frontmatter: Dict):
    """Creates a new "source" note containing the summary of the 
    MarkDownloaded document"""
    with open(SOURCE_TEMPLATE_PATH, "r") as f:
        template = f.read()

    fname = filename.split(".")[0]

    if frontmatter:
        url = frontmatter.get("url", "")
        template = template.replace("url: ", f"url: {url}")
        template = template.replace("{{title}}", new_filename.split(".")[0])
        template = template.replace("markdownload:", f'markdownload: "[[{fname}]]"')

    with open(f"{SOURCES_PATH}\\{new_filename}", "w", encoding="utf-8") as f:
        f.write(template + "\n" + summary)

def change_file_extension(filename: str, new_extension: str) -> str:
    """Change the extension of a filename."""
    return f"{os.path.splitext(filename)[0]}.{new_extension}"

def get_recording_date(file_path):
    """
    Extract the original recording date from an audio file.
    
    :param file_path: Path to the audio file
    :return: datetime object of the recording date or None if not found
    """
    try:
        audio = File(file_path)
        
        # Try to get date from metadata
        if audio is not None and audio.tags:
            if 'date' in audio.tags:
                date_str = str(audio.tags['date'][0])
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            elif 'creation_time' in audio.tags:
                return datetime.strptime(str(audio.tags['creation_time'][0]), "%Y-%m-%dT%H:%M:%S")
        
        # If metadata doesn't have date, try to parse from filename
        filename = os.path.basename(file_path)
        date_part = filename.split('-')[:3]  # Assumes format like "2024-05-01-pause-ai-france.m4a"
        if len(date_part) == 3:
            try:
                return datetime.strptime('-'.join(date_part), "%Y-%m-%d")
            except ValueError:
                pass
        
        # If all else fails, use file modification time
        return datetime.fromtimestamp(os.path.getmtime(file_path))
    
    except Exception as e:
        print(f"Error extracting date from {file_path}: {e}")
        # Return file modification time as a last resort
        return datetime.fromtimestamp(os.path.getmtime(file_path))

def generate_summary(category: str, transcription: str) -> str:
    """Generate a summary for a given transcription based on its category."""
    with open(f"prompts/summarise_{category.lower()}.md", "r") as f:
        prompt = f.read()
    return ai_model.message(prompt + transcription)

def transcribe_audio_files(input_dir: str, output_dir: str, category: str):
    """
    Transcribe audio files from input directory and save results in output directory.
    
    This function processes each audio file, generates a transcription using AssemblyAI,
    and saves the result as both JSON and markdown files.
    """
    for filename in os.listdir(input_dir):
        file_path = os.path.join(input_dir, filename)
        recording_date = get_recording_date(file_path)
        date_str = recording_date.strftime("%Y-%m-%d")
        
        json_filename = change_file_extension(filename, "json")
        md_filename = change_file_extension(filename, "md")
        
        if md_filename in os.listdir(output_dir) or filename in FILES_IN_TRANSCRIPTION:
            continue
        
        FILES_IN_TRANSCRIPTION.add(filename)
        print(f"Transcribing: {filename}", flush=True)
        
        transcript = transcriber.transcribe(file_path, config)
        
        # Save JSON response
        with open(os.path.join(output_dir, json_filename), "w") as f:
            json.dump(transcript.json_response, f)
        
        # Save markdown with speaker labels
        frontmatter = """---
tags:
  - transcription
""" 
        if category != "Unsorted":
            frontmatter += "  - " + {"Meetings": "meeting", "Ideas": "idea"}[category] + "\n"
        frontmatter += f"""date: {date_str}
---
"""
        text_with_speakers = "\n".join(f"Speaker {u.speaker} : {u.text}" for u in transcript.utterances)
        with open(os.path.join(output_dir, md_filename), "w", encoding='utf-8') as f:
            f.write(frontmatter+text_with_speakers)
        
        print(text_with_speakers)
        FILES_IN_TRANSCRIPTION.remove(filename)

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
            transcribe_audio_files(AUDIO_PATH.format(name=category), TRANSCRIPTIONS_PATH.format(name=category), category)
        except Exception:
            print(traceback.format_exc())

@slow_repeater.register
async def pull_gdocs():
    """Downloads and turns google docs into markdown"""
    try:
        for filename in os.listdir(GDOC_PATH):
            if not filename.endswith(".md"):
                continue
            with open(f"{GDOC_PATH}\\{filename}", "r", encoding="utf-8") as f:
                text = f.read()
            frontmatter = parse_frontmatter(text)
            if frontmatter.get("synced", True):
                continue
            url = frontmatter.get("url")
            if not url:
                continue
            FILES_IN_SUMMARIZATION.add(filename)

            # Downloading google doc as html
            gdoc_content_html = GDU.get_clean_document(url)

            print(f"Summarizing: {filename}", flush=True)
            gdoc_content_md = generate_summary("gdoc", gdoc_content_html)

            frontmatter["synced"] = True

            write_gdoc(gdoc_content_md, filename, frontmatter)

            print("DONE", flush=True)

            FILES_IN_SUMMARIZATION.remove(filename)

    except Exception:
        print(traceback.format_exc())

@slow_repeater.register
async def summarize_markdownloads():
    """Generate summaries for all the markdownload documents, and
    saves as a "source" note in Obsidian"""
    try:
        for filename in os.listdir(MARKDOWNLOAD_PATH):
            if not (filename.startswith("markdownload_") 
                    and filename.endswith(".md")):
                continue
            new_filename = filename[13:]
            if new_filename in os.listdir(SOURCES_PATH) or filename in FILES_IN_SUMMARIZATION:
                continue
            FILES_IN_SUMMARIZATION.add(filename)
            print(f"Summarizing: {filename}", flush=True)

            with open(f"{MARKDOWNLOAD_PATH}\\{filename}", "r", encoding="utf-8") as f:
                text = f.read()

            frontmatter = parse_frontmatter(text)
            
            summary = generate_summary("markdownload", text)

            write_md_summary(summary, filename, new_filename, frontmatter)

            FILES_IN_SUMMARIZATION.remove(filename)
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