import time
import logging
import sqlite3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Load configuration
# from config import PEOPLE_DIR, SCHEMA, DB_PATH # Old import
from config.config import PEOPLE_DIR, SCHEMA, DB_PATH # Corrected import

# Import database and sync functions
from database import initialize_database
from sync import sync_file_to_db, delete_file_from_db, initial_scan_and_sync

# Basic logging setup
# Update logger name for clarity
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - MAIN - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

class PeopleEventHandler(FileSystemEventHandler):
    """Handles file system events and triggers database synchronization."""
    def __init__(self, db_conn: sqlite3.Connection, schema: dict):
        self.db_conn = db_conn
        self.schema = schema
        # TODO: Add debounce mechanism if needed (to handle rapid saves)
        super().__init__()

    def on_modified(self, event):
        if event.is_directory:
            return
        # Check specifically for markdown files
        if not event.src_path.lower().endswith(".md"):
            logging.debug(f"Ignoring non-markdown file change: {event.src_path}")
            return

        logging.info(f"Event: Modified - {event.src_path}")
        try:
            sync_file_to_db(event.src_path, self.db_conn, self.schema)
        except Exception as e:
            logging.error(f"Error processing modification for {event.src_path}: {e}", exc_info=True)

    def on_created(self, event):
        # Often on_modified is triggered immediately after creation, covering this.
        # However, explicit handling might be desired.
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".md"):
             logging.debug(f"Ignoring non-markdown file creation: {event.src_path}")
             return

        logging.info(f"Event: Created - {event.src_path}")
        try:
            # Treat creation like modification
            sync_file_to_db(event.src_path, self.db_conn, self.schema)
        except Exception as e:
             logging.error(f"Error processing creation for {event.src_path}: {e}", exc_info=True)

    def on_deleted(self, event):
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".md"):
            logging.debug(f"Ignoring non-markdown file deletion: {event.src_path}")
            return

        logging.info(f"Event: Deleted - {event.src_path}")
        try:
            delete_file_from_db(event.src_path, self.db_conn, self.schema)
        except Exception as e:
             logging.error(f"Error processing deletion for {event.src_path}: {e}", exc_info=True)

    def on_moved(self, event):
        # Watchdog often reports move as delete(src) + create(dest)
        # Our ID-based logic in sync_file_to_db handles renames/moves during the create/modify event.
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".md") and not event.dest_path.lower().endswith(".md"):
             logging.debug(f"Ignoring non-markdown file move: {event.src_path} -> {event.dest_path}")
             return

        logging.info(f"Event: Moved - {event.src_path} to {event.dest_path}")
        # 1. Handle the deletion of the old path reference if needed (though delete event might cover this)
        try:
            delete_file_from_db(event.src_path, self.db_conn, self.schema)
        except Exception as e:
            logging.error(f"Error processing move (source deletion) for {event.src_path}: {e}", exc_info=True)

        # 2. Handle the creation/modification of the new path
        try:
            sync_file_to_db(event.dest_path, self.db_conn, self.schema)
        except Exception as e:
            logging.error(f"Error processing move (destination sync) for {event.dest_path}: {e}", exc_info=True)

if __name__ == "__main__":
    logging.info("--- Starting Obsidian Sync Script ---")
    if not SCHEMA:
        logging.error("Schema could not be loaded. Exiting.")
        exit(1)
    if not PEOPLE_DIR.exists() or not PEOPLE_DIR.is_dir():
         logging.error(f"People directory '{PEOPLE_DIR}' not found or not a directory. Exiting.")
         exit(1)

    logging.info(f"Database path: {DB_PATH}")
    logging.info(f"Watching directory: {PEOPLE_DIR}")
    logging.info(f"Using schema fields: {list(SCHEMA.keys())}")

    db_connection = None
    observer = None
    try:
        # Initialize DB connection
        db_connection = initialize_database(DB_PATH, SCHEMA)
        if not db_connection:
            logging.error("Failed to initialize database. Exiting.")
            exit(1)

        # Run Initial Scan Here
        initial_scan_and_sync(db_connection, SCHEMA)

        # Create and start the observer (AFTER initial scan)
        event_handler = PeopleEventHandler(db_connection, SCHEMA)
        observer = Observer()
        observer.schedule(event_handler, str(PEOPLE_DIR), recursive=True)
        observer.start()
        logging.info("File watcher started. Press Ctrl+C to stop.")

        # Keep the script running
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Stopping watcher...")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        if observer and observer.is_alive():
            observer.stop()
            observer.join()
            logging.info("Watcher stopped.")
        else:
             logging.info("Watcher was not running or already stopped.")

        if db_connection:
            db_connection.close()
            logging.info("Database connection closed.")
        logging.info("--- Obsidian Sync Script Finished ---") 