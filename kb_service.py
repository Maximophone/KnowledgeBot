import asyncio
import argparse
import logging # Import standard logging
from config import SLOW_REPEAT_INTERVAL # Added for scheduler interval
from config.paths import PATHS
from config.secrets import ASSEMBLY_AI_KEY, DISCORD_BOT_TOKEN
from config.logging_config import set_default_log_level, setup_logger # Added setup_logger
from typing import Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler # Added APScheduler

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

# Initialize logger for this module
logger = setup_logger(__name__)

# Initialize the scheduler
scheduler = AsyncIOScheduler()


def instantiate_all_processors(discord_io: DiscordIOCore) -> Dict[str, Any]:
    """Instantiates all processor classes and returns a dictionary mapping stage_name to instance."""
    processors = {}
    logger.info("Instantiating processors...") # Added logging

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
            # Use logger instead of print
            logger.error(f"Error instantiating {cls.__name__}: {e}", exc_info=True)
            # Decide if we should continue or raise

    # Add the non-NoteProcessor types manually if needed for registration
    processors["_transcriber"] = transcriber
    processors["_video_to_audio"] = video_to_audio_processor

    logger.info(f"Instantiated {len(processors)} processors.") # Added logging
    return processors


async def main():
    # Create all required directories
    for path in PATHS:
        if hasattr(path, 'parent') and path.suffix: # Check if it's likely a file path
             path.parent.mkdir(parents=True, exist_ok=True)
        elif not path.suffix and not path.exists(): # Check if it's likely a directory path and doesn't exist
             path.mkdir(parents=True, exist_ok=True)
    logger.info("Ensured all necessary directories exist.") # Added logging

    # Initialize Discord I/O Core
    logger.info("Initializing Discord...")
    discord_io = DiscordIOCore(token=DISCORD_BOT_TOKEN)
    discord_task = asyncio.create_task(discord_io.start_bot())
    logger.info("Discord task created.")

    # Instantiate all processors
    all_processors = instantiate_all_processors(discord_io)

    # Schedule processors
    logger.info("Scheduling processor jobs...")
    interval = SLOW_REPEAT_INTERVAL # Get interval from config, default 60s
    logger.info(f"Using scheduler interval: {interval} seconds")
    scheduled_count = 0
    for name, processor in all_processors.items():
         if hasattr(processor, 'process_all') and callable(processor.process_all):
            if isinstance(processor, NoteProcessor) and processor.stage_name:
                job_id = processor.stage_name
            else:
                job_id = name # Use the key like '_transcriber'

            logger.debug(f"Scheduling job: {job_id} with interval {interval}s")
            try:
                # Add jitter to potentially spread out initial runs slightly (e.g., up to 5 seconds)
                scheduler.add_job(processor.process_all, 'interval', seconds=interval, id=job_id, name=job_id, jitter=5)
                scheduled_count += 1
            except Exception as e:
                 logger.error(f"Error scheduling job {job_id}: {e}", exc_info=True) # Use logger
         else:
             logger.warning(f"Processor with key '{name}' has no process_all method, skipping scheduling.") # Use logger
    logger.info(f"Scheduled {scheduled_count} processor jobs.")


    try:
        # Start the scheduler
        logger.info("Starting scheduler...")
        scheduler.start()
        logger.info("Scheduler started.")

        logger.info("Gathering main tasks (Discord Bot)...") # Updated log message
        await asyncio.gather(
            discord_task, # Ensure Discord bot runs
            # No explicit task for the scheduler itself needed here,
            # gather just needs to keep the event loop alive.
            # Keep the scheduler running indefinitely
            asyncio.Event().wait() # Keep the main loop alive until interrupted
       )
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    except Exception as e:
        logger.error(f"An error occurred in the main gather loop: {e}", exc_info=True)
    finally:
        logger.info("Shutting down scheduler...")
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler shut down.")
        else:
            logger.info("Scheduler was not running.")
        # asyncio.gather usually handles cancellation of its awaited tasks on exit/exception.
        # If specific cleanup is needed for obsidian_ai_task or keyboard_listener_task,
        # they might need explicit cancellation here. -> Removed as tasks are moved


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Knowledge Bot Processor Service') # Updated description
    parser.add_argument('--log-level',
                        type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the default logging level (default: INFO)')
    args = parser.parse_args()

    # Set the default logging level
    set_default_log_level(args.log_level)
    logger.info(f"Logging level set to {args.log_level}") # Log level confirmation

    # Silence APScheduler executor logs below WARNING level
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    logger.info("Set APScheduler executor default logging level to WARNING to reduce noise.")

    # Run the main async function
    try:
        logger.info("Starting Knowledge Bot Processor Service...") # Updated log message
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Processor Service Application interrupted by user (KeyboardInterrupt).") # Updated log message
    except Exception as e:
        logger.critical(f"Processor Service Application exited unexpectedly: {e}", exc_info=True) # Updated log message
    finally:
        logger.info("Knowledge Bot Processor Service stopped.") # Updated log message
