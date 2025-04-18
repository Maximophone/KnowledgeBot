import asyncio
import argparse
from config.paths import PATHS
from config.secrets import ASSEMBLY_AI_KEY, DISCORD_BOT_TOKEN
from config.logging_config import set_default_log_level
from typing import Dict, Any

# Import processor classes
from processors.audio.transcriber import AudioTranscriber
from processors.notes.meditation import MeditationProcessor
from processors.notes.ideas import IdeaProcessor
from processors.notes.gdoc import GDocProcessor
from processors.notes.coda import CodaProcessor
from processors.notes.markdownload import MarkdownloadProcessor
from processors.notes.speaker_identifier import SpeakerIdentifier
from processors.notes.meeting import MeetingProcessor
from processors.notes.meeting_summary import MeetingSummaryProcessor
from processors.notes.transcript_classifier import TranscriptClassifier
from processors.notes.conversation import ConversationProcessor
from processors.notes.diary import DiaryProcessor
from processors.notes.idea_cleanup import IdeaCleanupProcessor
from processors.notes.todo import TodoProcessor
from processors.notes.interaction_logger import InteractionLogger
from processors.audio.video_to_audio import VideoToAudioProcessor
# Import base class for type checking
from processors.notes.base import NoteProcessor
# Import the new processor
from processors.notes.gdoc_uploader import GDocUploadProcessor

from integrations.discord import DiscordIOCore

from services.keyboard_listener import main as keyboard_listener_main

# Import existing services
from obsidian.obsidian_ai import process_file, needs_answer, VAULT_PATH
from services.file_watcher import start_file_watcher
from services.repeater import slow_repeater, start_repeaters


async def run_obsidian_ai():
    await start_file_watcher(VAULT_PATH, process_file, needs_answer, use_polling=True)

def instantiate_all_processors(discord_io: DiscordIOCore) -> Dict[str, Any]:
    """Instantiates all processor classes and returns a dictionary mapping stage_name to instance."""
    processors = {}

    # Instantiate audio processors (They don't have stage_name class attribute directly)
    transcriber = AudioTranscriber(
        input_dir=PATHS.audio_input,
        output_dir=PATHS.transcriptions,
        processed_dir=PATHS.audio_processed,
        api_key=ASSEMBLY_AI_KEY
    )
    # Note: AudioTranscriber needs special handling for registration/reset if needed
    # For now, we might store it differently or exclude from stage-based reset
    # processors["audio_transcriber"] = transcriber # Example key

    video_to_audio_processor = VideoToAudioProcessor(
        input_dir=PATHS.audio_input,
        output_dir=PATHS.audio_input,
        processed_dir=PATHS.audio_processed
    )
    # processors["video_to_audio"] = video_to_audio_processor # Example key

    # Instantiate note processors
    note_processor_classes = [
        MeditationProcessor,
        IdeaProcessor,
        GDocProcessor,
        CodaProcessor,
        MarkdownloadProcessor,
        SpeakerIdentifier,
        MeetingProcessor,
        MeetingSummaryProcessor,
        TranscriptClassifier,
        ConversationProcessor,
        DiaryProcessor,
        IdeaCleanupProcessor,
        TodoProcessor,
        InteractionLogger,
        GDocUploadProcessor
    ]

    for cls in note_processor_classes:
        if not issubclass(cls, NoteProcessor):
            continue # Should not happen based on list above

        if not cls.stage_name:
            print(f"Warning: Processor class {cls.__name__} missing stage_name attribute.")
            continue

        # Basic instantiation - assumes input_dir is the only common arg
        # We need to handle processors with different __init__ signatures
        try:
            if cls is MeditationProcessor:
                instance = cls(input_dir=PATHS.transcriptions, output_dir=PATHS.meditations)
            elif cls is IdeaProcessor:
                instance = cls(input_dir=PATHS.transcriptions, directory_file=PATHS.ideas_directory)
            elif cls is GDocProcessor:
                instance = cls(input_dir=PATHS.gdoc_path)
            elif cls is CodaProcessor:
                instance = cls(input_dir=PATHS.coda_path)
            elif cls is MarkdownloadProcessor:
                instance = cls(input_dir=PATHS.markdownload_path, output_dir=PATHS.sources_path, template_path=PATHS.source_template_path)
            elif cls is SpeakerIdentifier:
                instance = cls(input_dir=PATHS.transcriptions, discord_io=discord_io)
            elif cls is MeetingProcessor:
                instance = cls(input_dir=PATHS.transcriptions, output_dir=PATHS.meetings, template_path=PATHS.meeting_template)
            elif cls is MeetingSummaryProcessor:
                instance = cls(input_dir=PATHS.meetings, transcript_dir=PATHS.transcriptions)
            elif cls is TranscriptClassifier:
                instance = cls(input_dir=PATHS.transcriptions)
            elif cls is ConversationProcessor:
                instance = cls(input_dir=PATHS.conversations)
            elif cls is DiaryProcessor:
                instance = cls(input_dir=PATHS.transcriptions, output_dir=PATHS.diary)
            elif cls is IdeaCleanupProcessor:
                instance = cls(input_dir=PATHS.transcriptions, output_dir=PATHS.ideas)
            elif cls is TodoProcessor:
                instance = cls(input_dir=PATHS.transcriptions, directory_file=PATHS.todo_directory)
            elif cls is InteractionLogger:
                instance = cls(input_dir=PATHS.transcriptions)
            elif cls is GDocUploadProcessor:
                instance = cls(input_dir=PATHS.transcriptions, gdrive_folder_id=PATHS.meetings_gdrive_folder_id)

            processors[cls.stage_name] = instance

        except Exception as e:
            print(f"Error instantiating {cls.__name__}: {e}")
            # Decide if we should continue or raise

    # Add the non-NoteProcessor types manually if needed for registration
    # These won't be in the stage_name map used by the dashboard reset
    processors["_transcriber"] = transcriber
    processors["_video_to_audio"] = video_to_audio_processor

    return processors


async def setup_processors():
    """Initialize and register all processors."""

    # Initialize Discord I/O Core - needed for some processor instantiations
    discord_io = DiscordIOCore(token=DISCORD_BOT_TOKEN)
    discord_task = asyncio.create_task(discord_io.start_bot())

    # Instantiate all processors using the new function
    all_processors = instantiate_all_processors(discord_io)

    # Register all processors with the repeater using a loop
    for name, processor in all_processors.items():
        if hasattr(processor, 'process_all') and callable(processor.process_all):
            # Use the instance's actual stage_name if it's a NoteProcessor, otherwise use the dict key
            if isinstance(processor, NoteProcessor) and processor.stage_name:
                registration_name = processor.stage_name
            else:
                registration_name = name # Use the key for _transcriber, _video_to_audio

            print(f"Registering processor: {registration_name}")
            slow_repeater.register(processor.process_all, name=registration_name)
        else:
            print(f"Warning: Processor with key '{name}' has no process_all method.")

    # Return the discord_task to ensure it stays alive
    return discord_task


async def run_processor_services():
    """Setup and start all processor services."""
    discord_task = await setup_processors()
    await start_repeaters()
    # Keep the Discord task alive
    await discord_task


async def main():
    # Create all required directories
    for path in PATHS:
        if hasattr(path, 'parent') and path.suffix: # Check if it's likely a file path
             path.parent.mkdir(parents=True, exist_ok=True)

    # Start both service groups
    obsidian_ai_task = asyncio.create_task(run_obsidian_ai())
    processor_task = asyncio.create_task(run_processor_services())

    keyboard_listener_task = asyncio.create_task(keyboard_listener_main())

    await asyncio.gather(obsidian_ai_task, processor_task, keyboard_listener_task)


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Knowledge Bot Service')
    parser.add_argument('--log-level',
                        type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the default logging level (default: INFO)')
    args = parser.parse_args()

    # Set the default logging level
    set_default_log_level(args.log_level)

    # Run the main async function
    asyncio.run(main())
