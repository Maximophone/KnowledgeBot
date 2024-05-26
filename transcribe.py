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

from pyannote.audio import Pipeline
from pyannote.core import Segment

CATEGORIES = ["Meetings", "Ideas", "Unsorted"]

AUDIO_PATH = "G:\\My Drive\\Projects\\KnowledgeBot\\Audio\\{name}"
SUMMARIES_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}"
TRANSCRIPTIONS_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}\\Transcriptions"
IMPROVED_PATH = "G:\\My Drive\\Obsidian\\KnowledgeBot\\{name}\\Improved"

BEING_TRANSCRIBED = set()
BEING_SUMMARISED = set()
BEING_IMPROVED = set()

gemini = AI("gemini1.5")
gpt4o = AI("gpt4o")
ai_model = gpt4o

with open("prompts/summarise_meetings.md", "r") as f:
    SUM_MEETING_PROMPT = f.read()

def change_file_extension(fname: str, new_extension: str) -> str:
    return fname.split(".")[0] + "." + new_extension

def transcribe_meeting(audio_folder:str, filename: str):
    return model.transcribe(f"{audio_folder}/{filename}")

def diarize_audio(audio_path: str):
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization")
    diarization = pipeline(audio_path)
    return diarization

def format_diarization(diarization) -> str:
    formatted = ""
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        formatted += f"{speaker}: {turn.start:.1f}s - {turn.end:.1f}s\n"
    return formatted

def transcribe_and_diarize(audio_folder: str, filename: str):
    transcription = transcribe_meeting(audio_folder, filename)
    diarization = diarize_audio(f"{audio_folder}/{filename}")
    formatted_diarization = format_diarization(diarization)
    transcription["diarization"] = formatted_diarization
    return transcription

def summarise_generic(typ: str, transcription: str) -> str:
    with open(f"prompts/summarise_{typ.lower()}.md", "r") as f:
        prompt = f.read()
    return ai_model.message(prompt + transcription)

def summarise_meeting(meeting_transcription: str) -> str:
    return ai_model.message(SUM_MEETING_PROMPT + meeting_transcription)

def transcribe_and_save(transcription_input: str, transcription_output: str):
    for fname in os.listdir(transcription_input):
        new_fname = change_file_extension(fname, "json")
        md_fname = change_file_extension(fname, "md")
        if new_fname in os.listdir(transcription_output):
            # already transcribed, we skip it
            continue
        if fname in BEING_TRANSCRIBED:
            # currently being processed, we skip it
            continue
        BEING_TRANSCRIBED.add(fname)
        print(f"Transcribing: {fname}", flush=True)
        result = transcribe_and_diarize(transcription_input, fname)
        with open(f"{transcription_output}/{new_fname}", "w") as f:
            json.dump(result, f)
        text = result["text"]
        decoded_text = json.loads(f'"{text}"')
        with open(f"{transcription_output}/{md_fname}", "w", encoding='utf-8') as f:
            f.write(decoded_text)
        BEING_TRANSCRIBED.remove(fname)

def extract_temp(input: str, output: str):
    for fname in os.listdir(input):
        if fname.endswith("md"):
            continue
        new_fname = change_file_extension(fname, "md")
        if new_fname in os.listdir(output):
            # already transcribed, we skip it
            continue
        print(f"Temp extraction: {fname}", flush=True)
        with open(f"{input}/{fname}", "r", encoding='utf-8') as f:
            result = json.load(f)
        # Decode the Unicode escape sequences
        text = result["text"]
        decoded_text = json.loads(f'"{text}"')
        with open(f"{output}/{new_fname}", "w", encoding='utf-8') as f:
            f.write(decoded_text)

def prune_transcript(transcript: Dict) -> Dict:
    """We keep only the segments and language section, and we modify the segments"""
    new_transcript = {
        "language": transcript["language"],
        "segments": []
    }
    for segment in transcript["segments"]:
        for key in ["id", "tokens"]:
            segment.pop(key, None)
        new_transcript["segments"].append(segment)
    return new_transcript

def improve_transcription(pruned_transcript_json: Dict):
    pruned_transcript_txt = json.dumps(pruned_transcript_json)
    with open(f"prompts/improve_transcription.md", "r") as f:
        prompt = f.read()
    return ai_model.message(prompt + pruned_transcript_txt)

def improve_transcription_and_save(input: str, output: str):
    for fname in os.listdir(input):
        new_fname = change_file_extension(fname, "md")
        if new_fname in os.listdir(output):
            # already transcribed, we skip it
            continue
        if fname in BEING_IMPROVED:
            # currently being processed, we skip it
            continue
        BEING_IMPROVED.add(fname)
        with open(f"{input}/{fname}", "r") as f:
            result = json.load(f)
        pruned = prune_transcript(result)
        print(f"Improving Transcription: {fname}", flush=True)
        result = improve_transcription(pruned)
        with open(f"{output}/{new_fname}", "w") as f:
            f.write(result)
        BEING_IMPROVED.remove(fname)

def summarise_and_save(typ: str, summary_input: str, summary_output: str):
    for fname in os.listdir(summary_input):
        if not fname.endswith("json"):
            continue
        new_fname = change_file_extension(fname, "md")
        if new_fname in os.listdir(summary_output):
            # already summarised, we skip it
            continue
        if fname in BEING_SUMMARISED:
            # currently being processed, we skip it
            continue
        BEING_SUMMARISED.add(fname)
        with open(f"{summary_input}/{fname}", "r") as f:
            result = json.load(f)
        print(f"Summarising: {fname}", flush=True)
        summary = summarise_generic(typ, result["text"])
        with open(f"{summary_output}/{new_fname}", "w") as f:
            f.write(summary)
        BEING_SUMMARISED.remove(fname)

@slow_repeater.register
async def transcribe_all():
    for name in CATEGORIES:
        try:
            transcribe_and_save(AUDIO_PATH.format(name=name), TRANSCRIPTIONS_PATH.format(name=name))
        except Exception:
            print(traceback.format_exc())

@slow_repeater.register
async def temp():
    for name in CATEGORIES:
        try:
            extract_temp(TRANSCRIPTIONS_PATH.format(name=name), TRANSCRIPTIONS_PATH.format(name=name))
        except Exception:
            print(traceback.format_exc())

#@slow_repeater.register
async def improve_all():
    for name in CATEGORIES:
        try:
            improve_transcription_and_save(TRANSCRIPTIONS_PATH.format(name=name), IMPROVED_PATH.format(name=name))
        except Exception:
            print(traceback.format_exc())

@slow_repeater.register
async def summarise_all():
    for name in CATEGORIES:
        try:
            summarise_and_save(name, TRANSCRIPTIONS_PATH.format(name=name), SUMMARIES_PATH.format(name=name))
        except Exception:
            print(traceback.format_exc())

async def main():
    await start_repeaters()

with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

if torch.cuda.is_available():
    print("Computing on GPU")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = whisper.load_model("small", device=device)

if __name__ == "__main__":
    asyncio.run(main())