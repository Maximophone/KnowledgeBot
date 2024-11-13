import asyncio
from config.paths import PATHS
from config.secrets import ASSEMBLY_AI_KEY

# Import processors
from processors.audio.transcriber import AudioTranscriber
from processors.notes.meditation import MeditationProcessor
from processors.notes.ideas import IdeaProcessor
from processors.notes.gdoc import GDocProcessor
from processors.notes.markdownload import MarkdownloadProcessor
from processors.notes.speaker_identifier import SpeakerIdentifier
from processors.notes.meeting import MeetingProcessor
from processors.notes.meeting_summary import MeetingSummaryProcessor

# Import existing services
from obsidian_ai import process_file, needs_answer, VAULT_PATH
from file_watcher import start_file_watcher
from repeater import slow_repeater, start_repeaters

async def run_obsidian_ai():
    await start_file_watcher(VAULT_PATH, process_file, needs_answer, use_polling=True)

async def setup_processors():
    """Initialize and register all processors."""
    
    # Initialize audio transcriber
    transcriber = AudioTranscriber(
        input_dir=PATHS.audio_input,
        output_dir=PATHS.transcriptions,
        processed_dir=PATHS.audio_processed,
        api_key=ASSEMBLY_AI_KEY
    )
    
    # Initialize note processors
    meditation_processor = MeditationProcessor(
        input_dir=PATHS.transcriptions,
        output_dir=PATHS.meditations
    )
    
    idea_processor = IdeaProcessor(
        input_dir=PATHS.transcriptions,
        directory_file=PATHS.ideas_directory
    )

    gdoc_processor = GDocProcessor(
        input_dir=PATHS.gdoc_path
    )

    markdownload_processor = MarkdownloadProcessor(
        input_dir=PATHS.markdownload_path,
        output_dir=PATHS.sources_path,
        template_path=PATHS.source_template_path
    )

    speaker_identifier_processor = SpeakerIdentifier(
        input_dir=PATHS.transcriptions
    )

    meeting_processor = MeetingProcessor(
        input_dir=PATHS.transcriptions,
        output_dir=PATHS.meetings,
        template_path=PATHS.meeting_template
    )

    meeting_summary_processor = MeetingSummaryProcessor(
        input_dir=PATHS.meetings,
        transcript_dir=PATHS.transcriptions
    )
    
    # Register all processors with the repeater
    slow_repeater.register(transcriber.process_all)
    slow_repeater.register(meditation_processor.process_all)
    slow_repeater.register(idea_processor.process_all)
    slow_repeater.register(gdoc_processor.process_all)
    slow_repeater.register(markdownload_processor.process_all)
    slow_repeater.register(speaker_identifier_processor.process_all)
    slow_repeater.register(meeting_processor.process_all)
    slow_repeater.register(meeting_summary_processor.process_all)

async def run_processor_services():
    """Setup and start all processor services."""
    await setup_processors()
    await start_repeaters()

async def main():
    # Create all required directories
    for path in PATHS:
        path.mkdir(parents=True, exist_ok=True)
    
    # Start both service groups
    obsidian_ai_task = asyncio.create_task(run_obsidian_ai())
    processor_task = asyncio.create_task(run_processor_services())

    await asyncio.gather(obsidian_ai_task, processor_task)

if __name__ == "__main__":
    asyncio.run(main())

# import asyncio
# from obsidian_ai import process_file, needs_answer, VAULT_PATH
# from file_watcher import start_file_watcher
# from transcribe import (
#     create_required_directories,
#     start_repeaters
# )

# async def run_obsidian_ai():
#     await start_file_watcher(VAULT_PATH, process_file, needs_answer, use_polling=True)

# async def run_transcribe_services():
#     create_required_directories()
#     await start_repeaters()

# async def main():
#     obsidian_ai_task = asyncio.create_task(run_obsidian_ai())
#     transcribe_task = asyncio.create_task(run_transcribe_services())

#     await asyncio.gather(obsidian_ai_task, transcribe_task)

# if __name__ == "__main__":
#     asyncio.run(main())