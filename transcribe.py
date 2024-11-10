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

VAULT_PATH = "G:\\My Drive\\Obsidian"
KNOWLEDGEBOT_PATH = f"{VAULT_PATH}\\KnowledgeBot"
MARKDOWNLOAD_PATH = f"{VAULT_PATH}\\MarkDownload"
GDOC_PATH = f"{VAULT_PATH}\\gdoc"
SOURCES_PATH = f"{VAULT_PATH}\\Source"
SOURCE_TEMPLATE_PATH = f"{VAULT_PATH}\\Templates\\source.md"

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
    """Process transcriptions categorized as meditations.
    Creates a simplified, summarized version in the Meditations folder."""
    
    input_dir = TRANSCRIPTIONS_PATH
    output_dir = f"{KNOWLEDGEBOT_PATH}\\Meditations"
    os.makedirs(output_dir, exist_ok=True)
    
    for filename in os.listdir(input_dir):
        if not filename.endswith('.md'):
            continue
            
        # Check if this is a meditation transcription
        if "- meditation -" not in filename.lower():
            continue
            
        # Generate output filename (same as input but in different folder)
        output_file = os.path.join(output_dir, filename)
        if os.path.exists(output_file):
            continue
            
        if filename in FILES_IN_IMPROVEMENT:
            continue
            
        FILES_IN_IMPROVEMENT.add(filename)
        print(f"Processing meditation: {filename}", flush=True)
        
        try:
            # Read the transcription
            with open(os.path.join(input_dir, filename), 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse frontmatter and transcript
            frontmatter = parse_frontmatter(content)
            transcript = content.split('---', 2)[2].strip()
            
            # Generate title and summary
            title = generate_meditation_title(transcript)
            summary = generate_meditation_summary(transcript)
            
            # Create markdown content
            date_str = frontmatter.get('date', '')
            original_file = frontmatter.get('original_file', '')
            sanitized_filename = original_file.replace(" ", "%20")
            audio_link = f"G:/My Drive/KnowledgeBot/Audio/Processed/{sanitized_filename}"
            
            markdown_content = create_meditation_markdown(
                title=title,
                date=date_str,
                audio_link=audio_link,
                summary=summary,
                transcription=transcript
            )
            
            # Save processed file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
                
            print(f"Processed meditation: {filename}", flush=True)
            
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}", flush=True)
            traceback.print_exc()
        finally:
            FILES_IN_IMPROVEMENT.remove(filename)

@slow_repeater.register
async def process_ideas():
    """Process transcriptions categorized as ideas.
    Extracts individual ideas and adds them to the ideas directory."""
    
    input_dir = TRANSCRIPTIONS_PATH
    ideas_directory_path = f"{KNOWLEDGEBOT_PATH}\\Ideas Directory.md"
    
    # Create ideas directory if it doesn't exist
    os.makedirs(os.path.dirname(ideas_directory_path), exist_ok=True)
    if not os.path.exists(ideas_directory_path):
        # Initialize the ideas directory with frontmatter
        with open(ideas_directory_path, "w", encoding="utf-8") as f:
            f.write("""---
tags:
  - ideas
  - directory
---
# Ideas Directory

""")

    # Read existing directory to check which files have been processed
    with open(ideas_directory_path, "r", encoding="utf-8") as f:
        directory_content = f.read()
    
    for filename in os.listdir(input_dir):
        if not filename.endswith('.md'):
            continue
            
        # Check if this is an idea transcription
        if "- idea -" not in filename.lower():
            continue
            
        # Skip if this file has already been processed
        if f"[[{filename}]]" in directory_content:
            continue
            
        if filename in FILES_IN_IMPROVEMENT:
            continue
            
        FILES_IN_IMPROVEMENT.add(filename)
        print(f"Processing ideas from: {filename}", flush=True)
        
        try:
            # Read the transcription
            with open(os.path.join(input_dir, filename), 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse frontmatter and transcript
            frontmatter = parse_frontmatter(content)
            transcript = content.split('---', 2)[2].strip()
            
            # Extract individual ideas
            ideas_prompt = """Analyze this transcript and extract ALL distinct ideas, even if some are only briefly mentioned.
            
            Important guidelines:
            - Only split into multiple ideas if the transcript clearly discusses completely different, unrelated topics
            - Most transcripts should result in just one idea
            - For each idea, provide:
                1. A specific, searchable title (3-7 words)
                2. A concise summary that captures the essence in 1-2 short sentences
            
            Format your response as:
            ### {Title}
            {Concise summary focusing on the core concept, written in clear, direct language}
            
            Example format:
            ### Spaced Repetition for Habit Formation
            Using spaced repetition algorithms to optimize habit trigger timing, adapting intervals based on adherence data.
            
            ### Personal Knowledge Graph with Emergence
            A note-taking system where connections between notes evolve automatically based on semantic similarity and usage patterns.
            
            Transcript:
            """
            ideas_text = ai_model.message(ideas_prompt + transcript)
            
            # Prepare the content to append
            date_str = frontmatter.get('date', '')
            append_content = f"\n## Ideas from [[{filename}]] - {date_str}\n\n{ideas_text}\n\n---\n"
            
            # Append to ideas directory
            with open(ideas_directory_path, "a", encoding="utf-8") as f:
                f.write(append_content)
                
            print(f"Processed ideas from: {filename}", flush=True)
            
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}", flush=True)
            traceback.print_exc()
        finally:
            FILES_IN_IMPROVEMENT.remove(filename)

# Add this function to create necessary directories
def create_required_directories():
    """Create all required directories if they don't exist."""
    directories = [
        AUDIO_INPUT_PATH,
        AUDIO_PROCESSED_PATH,
        MARKDOWNLOAD_PATH,
        GDOC_PATH,
        SOURCES_PATH,
        TRANSCRIPTIONS_PATH,
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