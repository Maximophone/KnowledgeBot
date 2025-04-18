import os
import json
import sys
from pathlib import Path
from datetime import datetime
import logging
import time
import importlib # Needed for dynamic imports if classes aren't imported directly

# --- Configuration ---
# Add project root to sys.path to allow importing from parent directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Now import config and utils
try:
    from config.paths import PATHS
    # Attempt to import the frontmatter functions directly
    # Ensure processors path is included
    if str(PROJECT_ROOT / 'processors') not in sys.path:
         sys.path.insert(0, str(PROJECT_ROOT / 'processors'))
    from common.frontmatter import read_front_matter, update_front_matter
    # Import the function to get processor instances
    from kb_service import instantiate_all_processors
    # Import specific classes needed for hasattr checks
    from processors.notes.speaker_identifier import SpeakerIdentifier
    from processors.notes.interaction_logger import InteractionLogger
    from processors.notes.gdoc_uploader import GDocUploadProcessor
    # Add other processor classes here as they get reset methods
    # from processors.notes.todo import TodoProcessor

except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Ensure the dashboard is run from the project root or adjust sys.path accordingly.")
    sys.exit(1)

# --- Constants ---
# Mapping from stage_name to the processor *class* that handles it
# This is used to check if a reset method exists for the UI.
PROCESSOR_CLASSES = {
    SpeakerIdentifier.stage_name: SpeakerIdentifier,
    InteractionLogger.stage_name: InteractionLogger,
    GDocUploadProcessor.stage_name: GDocUploadProcessor,
    # Add other processors here as they get reset methods
    # TodoProcessor.stage_name: TodoProcessor,
}

# Determine the directory containing the notes to scan
# TODO: Make this configurable or discover multiple paths?
NOTES_DIR = PATHS.transcriptions

# Path to the status index file within the dashboard directory
INDEX_FILE_PATH = Path(__file__).parent / 'data' / 'processing_status.json'

# Ensure data directory exists
INDEX_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Core Functions ---

def load_status_index():
    """Loads the current status index from the JSON file."""
    if not INDEX_FILE_PATH.exists():
        return {}
    try:
        with open(INDEX_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error loading status index {INDEX_FILE_PATH}: {e}")
        return {}

def save_status_index(index_data):
    """Saves the status index to the JSON file."""
    try:
        with open(INDEX_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, sort_keys=True)
        logging.info(f"Saved status index to {INDEX_FILE_PATH}")
    except IOError as e:
        logging.error(f"Error saving status index {INDEX_FILE_PATH}: {e}")

def update_status_index():
    """Scans the notes directory and updates the status index based on mtime."""
    logging.info(f"Starting status index update. Scanning: {NOTES_DIR}")
    if not NOTES_DIR.is_dir():
        logging.error(f"Notes directory not found: {NOTES_DIR}")
        return 0, 0, 0 # Indicate error or no files processed

    current_index = load_status_index()
    updated_files = 0
    new_files = 0
    deleted_files = 0
    processed_files = set() # Keep track of files found on disk

    start_time = time.time()

    for file_path in NOTES_DIR.rglob('*.md'): # Use rglob for recursive search
        filename = file_path.name
        processed_files.add(filename)
        try:
            current_mtime = file_path.stat().st_mtime
            cached_data = current_index.get(filename)

            # Check if file needs processing (new or modified)
            needs_update = not cached_data or cached_data.get('last_read_mtime') != current_mtime

            if not needs_update:
                continue

            # File is new or modified, read frontmatter
            logging.debug(f"Reading frontmatter for: {filename}")
            frontmatter = read_front_matter(file_path)
            if not frontmatter:
                 logging.warning(f"No frontmatter found in {filename}. Skipping index update for this file.")
                 # If the file exists in index, remove it or mark as invalid?
                 if filename in current_index:
                      del current_index[filename]
                      # Or mark: current_index[filename] = {"error": "No frontmatter"}
                 continue

            # Extract relevant data
            current_stages = frontmatter.get('processing_stages', [])
            stages_with_reset_info = []
            for stage in current_stages:
                processor_class = PROCESSOR_CLASSES.get(stage)
                is_resettable = hasattr(processor_class, 'reset') if processor_class else False
                stages_with_reset_info.append({"name": stage, "resettable": is_resettable})

            file_data = {
                'last_read_mtime': current_mtime,
                'processing_stages': stages_with_reset_info, # Store list of dicts now
                'title': frontmatter.get('title'),
                'category': frontmatter.get('category'),
                'date': str(frontmatter.get('date')) if frontmatter.get('date') else None # Ensure date is stringified
            }

            # Update the index
            current_index[filename] = file_data
            if cached_data:
                updated_files += 1
                logging.debug(f"Updated index for: {filename}")
            else:
                new_files += 1
                logging.info(f"Added new file to index: {filename}")

        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}", exc_info=True)

    # Check for deleted files
    existing_files = set(current_index.keys())
    deleted_filenames = existing_files - processed_files
    for filename in deleted_filenames:
        logging.info(f"Removing deleted file from index: {filename}")
        del current_index[filename]
        deleted_files += 1

    # Save the updated index
    save_status_index(current_index)
    end_time = time.time()
    duration = end_time - start_time
    logging.info(
        f"Status index update complete in {duration:.2f} seconds. "
        f"New: {new_files}, Updated: {updated_files}, Deleted: {deleted_files}, "
        f"Total indexed: {len(current_index)}"
    )
    return new_files, updated_files, deleted_files

# Note: reset_stage_for_file will be handled in app.py now, using instantiate_all_processors
# We can remove the old implementation from here if desired, or keep it as a non-API utility.
# For clarity, let's remove it for now.
# def reset_stage_for_file(filename: str, stage_name: str):
#    ...

# --- Main Execution (for testing) ---
if __name__ == "__main__":
    print("Running status manager directly for testing...")
    print(f"Using notes directory: {NOTES_DIR}")
    print(f"Using index file: {INDEX_FILE_PATH}")

    # Example: Perform an update
    update_status_index()

    # Example: Load and print the index
    index = load_status_index()
    print("\nCurrent Index Sample:")
    # Print first 5 items for brevity
    sample_index = {k: index[k] for k in list(index.keys())[:5]}
    print(json.dumps(sample_index, indent=2, sort_keys=True))

    print("\nStatus manager test finished.") 