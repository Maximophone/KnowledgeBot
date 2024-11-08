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
import json
from ai import AI
import asyncio
from repeater import slow_repeater, start_repeaters
import traceback
import assemblyai
from mutagen import File
from datetime import datetime
import aiofiles
import aiohttp

from gdoc_utils import GoogleDocUtils

AUDIO_INPUT_PATH = "G:\\My Drive\\KnowledgeBot\\Audio\\Incoming"
AUDIO_PROCESSED_PATH = "G:\\My Drive\\KnowledgeBot\\Audio\\Processed"
TRANSCRIPTIONS_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\Transcriptions"

# Define categories for organizing recordings
CATEGORIES_PROMPT = """
Based on this transcription, classify it into one of these categories: 
    - meeting (if it's a conversation between multiple people discussing work-related topics)
    - idea (if it's a monologue about new ideas, projects, or creative thoughts)
    - meditation (if it's the recording of a guided meditation)
    - unsorted (if it doesn't fit the other categories)
    
    Only respond with the category name, nothing else.
    
    Transcription:
"""
CATEGORIES = ["Meetings", "Ideas", "Unsorted", "Meditations"]
TRANSCRIPTION_CATEGORIES = ["Meetings", "Ideas", "Unsorted"]

VAULT_PATH = "G:\\My Drive\\Obsidian"
MARKDOWNLOAD_PATH = f"{VAULT_PATH}\\MarkDownload"
GDOC_PATH = f"{VAULT_PATH}\\gdoc"
SOURCES_PATH = f"{VAULT_PATH}\\Source"
SOURCE_TEMPLATE_PATH = f"{VAULT_PATH}\\Templates\\source.md"

# File paths for different stages of processing
AUDIO_PATH = "G:\\My Drive\\Projects\\KnowledgeBot\\Audio\\{name}"
SUMMARIES_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}"
#TRANSCRIPTIONS_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}\\Transcriptions"

TRANSCR_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\Transcriptions"

PROCESSED_FILES_TRACKER = "G:\\My Drive\\Obsidian\\KnowledgeBot\\processed_files_tracker.md"

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
haiku35 = AI("haiku3.5")
ai_model = sonnet35
small_ai_model = haiku35

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

###############################
# AI MODEL FUNCTIONS
###############################

def classify_transcription(text: str) -> str:
    """Classify the transcription into a category based on its content."""
    prompt = CATEGORIES_PROMPT
    return small_ai_model.message(prompt + text)

def generate_title(text: str) -> str:
    """Generate a short, descriptive title for the transcription."""
    prompt = """Generate a very short title (1-5 words) that captures the main topic or essence of this transcription.
    Only output the title, nothing else.
    
    Transcription:
    """
    return small_ai_model.message(prompt + text)

def generate_summary(category: str, transcription: str) -> str:
    """Generate a summary for a given transcription based on its category."""
    with open(f"prompts/summarise_{category.lower()}.md", "r") as f:
        prompt = f.read()
    return ai_model.message(prompt + transcription)

def generate_meditation_title(transcription: str) -> str:
    """Generate a short title for a meditation based on its transcription."""
    prompt = "Generate a very short title (3-6 words) that captures the essence of this meditation. ONLY OUTPUT THE TITLE, nothing else. Meditation transcript: \n\n"
    return ai_model.message(prompt + transcription).strip()

def generate_meditation_summary(transcription: str) -> str:
    """Generate a summary for a meditation (max 100 words)."""
    prompt = "Summarize this meditation in 100 words or less. ONLY OUTPUT THE SUMMARY, nothing else. Meditation transcript: \n\n"
    return ai_model.message(prompt + transcription).strip()

###############################
# END OF AI MODEL FUNCTIONS
###############################

def create_meditation_markdown(title: str, date: str, audio_link: str, summary: str, transcription: str) -> str:
    """Create a markdown file for a meditation."""
    return f"""# {title}

Date: {date}
[Audio Recording]({audio_link})

## Summary
{summary}

## Transcription
{transcription}
"""

async def process_single_file(file_path: str, output_dir: str, original_filename: str):
    """Process a single audio file: transcribe, classify, and save."""
    try:
        # Get recording date
        recording_date = get_recording_date(file_path)
        date_str = recording_date.strftime("%Y-%m-%d")
        
        # Transcribe
        transcript = await transcribe_audio_file(file_path, config)
        
        # Classify and generate title
        category = classify_transcription(transcript.text)
        title = None
        # Check if original filename starts with date pattern
        filename_without_ext = os.path.splitext(original_filename)[0]
        if filename_without_ext.startswith(date_str):
            # Extract everything after the date as title
            title_parts = filename_without_ext[len(date_str):].strip()
            if title_parts.startswith("-"):
                title = title_parts[1:].strip()  # Remove the " - " separator
                print(f"Using existing title from filename: {title}", flush=True)
        if title is None:
            # Otherwise, generate a new title
            title = generate_title(transcript.text)

        print(f"Classified as: {category}, Title: {title}", flush=True)
        
        # Create safe filename base (without extension)
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        base_filename = f"{date_str} - {category} - {safe_title}"
        
        # Save JSON response
        json_filename = f"{base_filename}.json"
        async with aiofiles.open(os.path.join(output_dir, json_filename), "w") as f:
            await f.write(json.dumps(transcript.json_response, indent=2))
        
        print(f"Saved JSON: {json_filename}", flush=True)

        # Prepare frontmatter
        frontmatter = f"""---
tags:
  - transcription
  - {category}
date: {date_str}
original_file: "{original_filename}"
title: "{title}"
json_data: "{json_filename}"
AutoNoteMover: "disable"
---
"""
        # Save markdown with speaker labels
        text_with_speakers = "\n".join(f"Speaker {u.speaker} : {u.text}" for u in transcript.utterances)
        full_content = frontmatter + "\n" + text_with_speakers
        
        md_filename = f"{base_filename}.md"

        async with aiofiles.open(os.path.join(output_dir, md_filename), "w", encoding='utf-8') as f:
            await f.write(full_content)
        
        print(f"Saved MD: {md_filename}", flush=True)

        # Move original file to processed folder
        os.makedirs(AUDIO_PROCESSED_PATH, exist_ok=True)
        os.rename(file_path, os.path.join(AUDIO_PROCESSED_PATH, original_filename))
        
        print(f"Processed: {original_filename} -> {md_filename}", flush=True)
        
    except Exception as e:
        print(f"Error processing {original_filename}: {str(e)}", flush=True)
        traceback.print_exc()
    finally:
        FILES_IN_TRANSCRIPTION.remove(original_filename)


async def transcribe_audio_file(file_path: str, config: assemblyai.TranscriptionConfig) -> assemblyai.Transcript:
    """Asynchronously transcribe a single audio file."""
    async with aiohttp.ClientSession():
        #TODO: Not async, to be fixed
        transcript = transcriber.transcribe(file_path, config)
    return transcript

async def transcribe_audio_files(input_dir: str, output_dir: str):
    """
    Transcribe audio files from input directory and save results in output directory.
    
    This function processes each audio file, generates a transcription using AssemblyAI,
    and saves the result as both JSON and markdown files.
    """
    tasks = []
    for filename in os.listdir(input_dir):
        file_path = os.path.join(input_dir, filename)
        
        # Skip if already being processed
        if filename in FILES_IN_TRANSCRIPTION:
            continue
        
        FILES_IN_TRANSCRIPTION.add(filename)
        print(f"Queuing transcription: {filename}", flush=True)

        task = asyncio.create_task(process_single_file(file_path, output_dir, filename))
        tasks.append(task)
    
    await asyncio.gather(*tasks)

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


def load_processed_files():
    processed_files = {}
    if os.path.exists(PROCESSED_FILES_TRACKER):
        with open(PROCESSED_FILES_TRACKER, 'r', encoding='utf-8') as f:
            current_category = None
            for line in f:
                line = line.strip()
                if line.startswith('## '):
                    current_category = line[3:]
                    processed_files[current_category] = {}
                elif line.startswith('- '):
                    parts = line[2:].split(' -> ')
                    if len(parts) == 2 and current_category:
                        processed_files[current_category][parts[0]] = parts[1]
    return processed_files

def save_processed_file(category, original_filename, processed_filename):
    processed_files = load_processed_files()
    if category not in processed_files:
        processed_files[category] = {}
    processed_files[category][original_filename] = processed_filename
    
    with open(PROCESSED_FILES_TRACKER, 'w', encoding='utf-8') as f:
        f.write("# Processed Files Tracker\n\n")
        f.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for cat, files in processed_files.items():
            f.write(f"## {cat}\n\n")
            for orig, proc in files.items():
                f.write(f"- {orig} -> {proc}\n")
            f.write("\n")

@slow_repeater.register
async def process_all_transcriptions():
    """Transcribe all audio files across relevant categories."""
    try:
        await transcribe_audio_files(AUDIO_INPUT_PATH, TRANSCRIPTIONS_PATH)
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
async def process_meditations():
    """Process meditation audio files."""
    input_dir = AUDIO_PATH.format(name="Meditations")
    output_dir = SUMMARIES_PATH.format(name="Meditations")
    processed_files = load_processed_files()
    processed_meditations = processed_files.get("Meditations", {})

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if filename in processed_meditations:
            continue  # Skip already processed files

        if filename in FILES_IN_TRANSCRIPTION or filename in FILES_IN_SUMMARIZATION:
            continue

        file_path = os.path.join(input_dir, filename)
        recording_date = get_recording_date(file_path)
        date_str = recording_date.strftime("%Y-%m-%d")

        # Transcribe
        FILES_IN_TRANSCRIPTION.add(filename)
        print(f"Transcribing meditation: {filename}", flush=True)
        try:
            transcript = transcriber.transcribe(file_path, config)
            if transcript is None or transcript.text is None:
                print(f"Error: Transcription failed for {filename}", flush=True)
                FILES_IN_TRANSCRIPTION.remove(filename)
                continue
        except Exception as e:
            print(f"Error transcribing {filename}: {str(e)}", flush=True)
            FILES_IN_TRANSCRIPTION.remove(filename)
            continue
        FILES_IN_TRANSCRIPTION.remove(filename)

        # Generate title and summary
        FILES_IN_SUMMARIZATION.add(filename)
        print(f"Summarizing meditation: {filename}", flush=True)
        try:
            title = generate_meditation_title(transcript.text)
            summary = generate_meditation_summary(transcript.text)
        except Exception as e:
            print(f"Error generating title or summary for {filename}: {str(e)}", flush=True)
            FILES_IN_SUMMARIZATION.remove(filename)
            continue
        FILES_IN_SUMMARIZATION.remove(filename)

        # Create markdown content
        sanitized_filename = filename.replace(" ", "%20")
        audio_link = f"G:/My Drive/Projects/KnowledgeBot/Audio/Meditations/{sanitized_filename}"
        markdown_content = create_meditation_markdown(title, date_str, audio_link, summary, transcript.text)

        # Save markdown file
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        markdown_filename = f"{date_str} - {safe_title}.md"
        markdown_path = os.path.join(output_dir, markdown_filename)
        with open(markdown_path, "w", encoding='utf-8') as f:
            f.write(markdown_content)

        # Update the tracker
        save_processed_file("Meditations", filename, markdown_filename)

        print(f"Processed meditation: {markdown_filename}", flush=True)

# Add this function to create necessary directories
def create_required_directories():
    """Create all required directories if they don't exist."""
    directories = [
        AUDIO_INPUT_PATH,
        AUDIO_PROCESSED_PATH
    ] + [
        AUDIO_PATH.format(name=category) for category in CATEGORIES
    ] + [
        SUMMARIES_PATH.format(name=category) for category in CATEGORIES
    ] + [
        TRANSCRIPTIONS_PATH.format(name=category) for category in TRANSCRIPTION_CATEGORIES
    ] + [
        MARKDOWNLOAD_PATH,
        GDOC_PATH,
        SOURCES_PATH,
        TRANSCR_PATH
    ]

    print("Creating directories...", flush=True)
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

# Update the main function to create directories before starting repeaters
async def main():
    """Main function to create directories and start all repeaters."""
    create_required_directories()
    await start_repeaters()

if __name__ == "__main__":
    asyncio.run(main())