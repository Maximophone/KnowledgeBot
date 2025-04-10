import asyncio
import argparse
from config.paths import PATHS
from config.secrets import ASSEMBLY_AI_KEY, DISCORD_BOT_TOKEN
from config.logging_config import set_default_log_level

# Import processors
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

from integrations.discord import DiscordIOCore

from services.keyboard_listener import main as keyboard_listener_main

# Import existing services
from obsidian.obsidian_ai import process_file, needs_answer, VAULT_PATH
from services.file_watcher import start_file_watcher
from services.repeater import slow_repeater, start_repeaters

async def run_obsidian_ai():
    await start_file_watcher(VAULT_PATH, process_file, needs_answer, use_polling=True)

async def setup_processors():
    """Initialize and register all processors."""
    
    # Initialize Discord I/O Core
    discord_io = DiscordIOCore(token=DISCORD_BOT_TOKEN)
    
    # Start Discord bot in a non-blocking way
    discord_task = asyncio.create_task(discord_io.start_bot())
    
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

    todo_processor = TodoProcessor(
        input_dir=PATHS.transcriptions,
        directory_file=PATHS.todo_directory
    )

    gdoc_processor = GDocProcessor(
        input_dir=PATHS.gdoc_path
    )

    coda_processor = CodaProcessor(
        input_dir=PATHS.coda_path
    )

    markdownload_processor = MarkdownloadProcessor(
        input_dir=PATHS.markdownload_path,
        output_dir=PATHS.sources_path,
        template_path=PATHS.source_template_path
    )

    speaker_identifier_processor = SpeakerIdentifier(
        input_dir=PATHS.transcriptions,
        discord_io=discord_io
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

    transcript_classifier_processor = TranscriptClassifier(
        input_dir=PATHS.transcriptions
    )

    conversation_processor = ConversationProcessor(
        input_dir=PATHS.conversations
    )

    diary_processor = DiaryProcessor(
        input_dir=PATHS.transcriptions,
        output_dir=PATHS.diary
    )

    idea_cleanup_processor = IdeaCleanupProcessor(
    input_dir=PATHS.transcriptions,
    output_dir=PATHS.ideas
    )

    interaction_logger_processor = InteractionLogger(
        input_dir=PATHS.transcriptions
    )

    video_to_audio_processor = VideoToAudioProcessor(
        input_dir=PATHS.audio_input,
        output_dir=PATHS.audio_input,
        processed_dir=PATHS.audio_processed
    )
    
    # Register all processors with the repeater
    slow_repeater.register(video_to_audio_processor.process_all, name="video_to_audio_processor")
    slow_repeater.register(transcriber.process_all, name="transcriber")
    slow_repeater.register(meditation_processor.process_all, name="meditation_processor")
    slow_repeater.register(idea_processor.process_all, name="idea_processor")
    slow_repeater.register(todo_processor.process_all, name="todo_processor")
    slow_repeater.register(gdoc_processor.process_all, name="gdoc_processor")
    slow_repeater.register(coda_processor.process_all, name="coda_processor")
    slow_repeater.register(markdownload_processor.process_all, name="markdownload_processor")
    slow_repeater.register(speaker_identifier_processor.process_all, name="speaker_identifier_processor")
    slow_repeater.register(meeting_processor.process_all, name="meeting_processor")
    slow_repeater.register(meeting_summary_processor.process_all, name="meeting_summary_processor")
    slow_repeater.register(transcript_classifier_processor.process_all, name="transcript_classifier_processor")
    slow_repeater.register(conversation_processor.process_all, name="conversation_processor")
    slow_repeater.register(diary_processor.process_all, name="diary_processor")
    slow_repeater.register(idea_cleanup_processor.process_all, name="idea_cleanup_processor")
    slow_repeater.register(interaction_logger_processor.process_all, name="interaction_logger_processor")
    
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
        path.mkdir(parents=True, exist_ok=True)
    
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
