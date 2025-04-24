import asyncio
import argparse
from config.paths import PATHS
from config.logging_config import set_default_log_level, setup_logger
from config import secrets # Necessary to load the dotenv file
from services.keyboard_listener import main as keyboard_listener_main
from obsidian.obsidian_ai import process_file, needs_answer # Import necessary functions/variables
from services.file_watcher import start_file_watcher

# Initialize logger for this module
logger = setup_logger(__name__)

async def run_obsidian_ai():
    """Starts the Obsidian file watcher."""
    logger.info("Starting Obsidian file watcher...")
    try:
        # Ensure the VAULT_PATH exists or handle appropriately if needed
        if not PATHS.vault_path.exists():
             logger.warning(f"Obsidian vault path not found: {PATHS.vault_path}. File watcher will not start.")
             return # Or raise an error
        await start_file_watcher(PATHS.vault_path, process_file, needs_answer, use_polling=True)
        logger.info("Obsidian file watcher finished.") # Should ideally run indefinitely
    except Exception as e:
        logger.error(f"Error in Obsidian file watcher: {e}", exc_info=True)
        # Consider if restart logic is needed

async def main():
    """Main function to run auxiliary services."""
    # Create directories relevant to these services if necessary (e.g., VAULT_PATH parent)
    # Simplified check - adjust if more paths managed by this service need creation
    try:
        if not PATHS.vault_path.exists():
             logger.info(f"Creating Obsidian vault directory (if needed): {PATHS.vault_path}")
             PATHS.vault_path.mkdir(parents=True, exist_ok=True)
        # Add other directory checks if needed by keyboard_listener or obsidian_ai components
    except Exception as e:
         logger.error(f"Error creating directories: {e}", exc_info=True)
         return # Stop if essential dirs can't be created

    logger.info("Starting auxiliary services...")
    obsidian_ai_task = asyncio.create_task(run_obsidian_ai())
    keyboard_listener_task = asyncio.create_task(keyboard_listener_main())

    try:
        logger.info("Gathering auxiliary tasks...")
        await asyncio.gather(obsidian_ai_task, keyboard_listener_task)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received for auxiliary services.")
    except Exception as e:
        logger.error(f"An error occurred in the auxiliary services main gather loop: {e}", exc_info=True)
    finally:
        logger.info("Auxiliary services shutting down...")
        # Cancel tasks if they are still running
        if not obsidian_ai_task.done():
            obsidian_ai_task.cancel()
        if not keyboard_listener_task.done():
            keyboard_listener_task.cancel()
        # Await cancellation
        # Use try-except for gather during cancellation as tasks might already be finished
        try:
            await asyncio.gather(obsidian_ai_task, keyboard_listener_task, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info("Tasks were cancelled.")
        logger.info("Auxiliary services stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Obsidian AI Watcher & Keyboard Listener Service') # Updated description
    parser.add_argument('--log-level',
                        type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the default logging level (default: INFO)')
    args = parser.parse_args()

    set_default_log_level(args.log_level)
    logger.info(f"Logging level set to {args.log_level}")

    try:
        logger.info("Starting Obsidian/Keyboard Service Application...") # Updated log message
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Obsidian/Keyboard Service Application interrupted by user.") # Updated log message
    except Exception as e:
        logger.critical(f"Obsidian/Keyboard Service Application exited unexpectedly: {e}", exc_info=True) # Updated log message
    finally:
        logger.info("Obsidian/Keyboard Service Application stopped.") # Updated log message 