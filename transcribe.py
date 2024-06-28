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
import subprocess
import assemblyai

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

with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)


gemini = AI("gemini1.5")
gpt4o = AI("gpt4o")
sonnet35 = AI("sonnet3.5")
ai_model = sonnet35

assemblyai.settings.api_key = secrets["assembly_ai"]
transcriber = assemblyai.Transcriber()
config = assemblyai.TranscriptionConfig(
  speaker_labels=True,
  language_detection=True
)

with open("prompts/summarise_meetings.md", "r") as f:
    SUM_MEETING_PROMPT = f.read()

def convert_to_wav(input_file, output_file):
    command = f'ffmpeg -i "{input_file}" "{output_file}"'
    subprocess.call(command, shell=True)

def change_file_extension(fname: str, new_extension: str) -> str:
    return fname.split(".")[0] + "." + new_extension

def transcribe_meeting(audio_folder:str, filename: str):
    return model.transcribe(f"{audio_folder}/{filename}")

def diarize_audio(audio_path: str):
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=secrets["hugging_face"]
        )
    diarization = pipeline(audio_path)
    return diarization

def format_diarization(diarization) -> str:
    formatted = ""
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        formatted += f"{speaker}: {turn.start:.1f}s - {turn.end:.1f}s\n"
    return formatted

def annotation_to_dict(annotation):
    segments = []
    for segment, _, label in annotation.itertracks(yield_label=True):
        segments.append({
            "start": segment.start,
            "end": segment.end,
            "label": label
        })
    return segments

def transcribe_and_diarize(audio_folder: str, filename: str):
    transcription = transcribe_meeting(audio_folder, filename)
    diarization = diarize_audio(f"{audio_folder}/{filename}")
    print(diarization)
    formatted_diarization = format_diarization(diarization)
    transcription["diarization"] = formatted_diarization
    transcription["diarization_segments"] = annotation_to_dict(diarization)
    return transcription

def summarise_generic(typ: str, transcription: str) -> str:
    with open(f"prompts/summarise_{typ.lower()}.md", "r") as f:
        prompt = f.read()
    return ai_model.message(prompt + transcription)

def summarise_meeting(meeting_transcription: str) -> str:
    return ai_model.message(SUM_MEETING_PROMPT + meeting_transcription)

def integrate_speakers(transcription_result: Dict) -> str:
    text = transcription_result["text"]
    diarization_segments = transcription_result["diarization_segments"]
    segments = transcription_result["segments"]

    #speaker_annotations = diarization_segments
    # for turn, _, speaker in diarization_segments.itertracks(yield_label=True):
    #     speaker_annotations.append((turn.start, turn.end, speaker))

    #for turn in diarization_segments:


    annotated_text = ""
    for segment in segments:
        segment_start = segment["start"]
        segment_end = segment["end"]
        segment_text = segment["text"]

        speaker = "Unknown"
        for annotation in diarization_segments:
            start = annotation["start"]
            end = annotation["end"]
            spk = annotation["label"]
            if start <= segment_start <= end:
                speaker = spk
                break

        annotated_text += f"{speaker}: {segment_text}\n"

    return annotated_text

def convert_to_wav_and_save(audio_dir: str):
    for fname in os.listdir(audio_dir):
        if fname.endswith(".wav"):
            continue
        wav_fname = change_file_extension(fname, "wav")
        if os.path.isfile(f"{audio_dir}/{wav_fname}"):
            continue
        convert_to_wav(
            f"{audio_dir}/{fname}",
            f"{audio_dir}/{wav_fname}"
        )

def transcribe_and_save(transcription_input: str, transcription_output: str):
    for fname in os.listdir(transcription_input):
        #if not fname.endswith(".wav"):
            # we only process wav files
        #    continue
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
        transcript = transcriber.transcribe(f"{transcription_input}/{fname}", config)
        #result = transcribe_and_diarize(transcription_input, fname)
        with open(f"{transcription_output}/{new_fname}", "w") as f:
            json.dump(transcript.json_response, f)
        text_with_speakers = ""
        for utterance in transcript.utterances:
            text_with_speakers += f"Speaker {utterance.speaker} : {utterance.text}\n"
        #text_with_speakers = integrate_speakers(result)
        print(text_with_speakers)
        with open(f"{transcription_output}/{md_fname}", "w", encoding='utf-8') as f:
            f.write(text_with_speakers)
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

#@slow_repeater.register
async def convert_to_wav_all():
    for name in CATEGORIES:
        try:
            convert_to_wav_and_save(AUDIO_PATH.format(name=name), TRANSCRIPTIONS_PATH.format(name=name))
        except Exception:
            print(traceback.format_exc())

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

if torch.cuda.is_available():
    print("Computing on GPU")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = whisper.load_model("small", device=device)

if __name__ == "__main__":
    #convert_to_wav_and_save("tests/data/transcription_in")
    #transcribe_and_save("tests/data/transcription_in", "tests/data/transcription_out")
    asyncio.run(main())