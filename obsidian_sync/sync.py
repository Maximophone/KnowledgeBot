import logging
import uuid
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from ruamel.yaml import YAML
from ruamel.yaml.scanner import ScannerError
from ruamel.yaml.parser import ParserError

from config.config import SCHEMA, PEOPLE_DIR
from database import upsert_person, delete_person_by_id, get_id_by_filepath

# Initialize YAML parser (using ruamel.yaml for comment/format preservation)
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# Update logger name for clarity
log = logging.getLogger("SYNC")
log.setLevel(logging.INFO)
# Avoid duplicate handlers if root logger is configured
if not log.handlers:
     handler = logging.StreamHandler()
     formatter = logging.Formatter('%(asctime)s - %(levelname)s - SYNC - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
     handler.setFormatter(formatter)
     log.addHandler(handler)

# --- Frontmatter Parsing --- #

def parse_frontmatter(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parses YAML frontmatter from a Markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.startswith('---'):
            return {} # No frontmatter found

        parts = content.split('---', 2)
        if len(parts) < 3:
            return {} # Malformed frontmatter section

        frontmatter_str = parts[1].strip()
        if not frontmatter_str:
            return {} # Empty frontmatter

        # Use ruamel.yaml to load
        data = yaml.load(frontmatter_str)
        return data if isinstance(data, dict) else {}

    except (ScannerError, ParserError) as e:
        log.error(f"YAML parsing error in file {file_path}: {e}")
        return None # Indicate error
    except FileNotFoundError:
        log.error(f"File not found for parsing: {file_path}")
        return None
    except Exception as e:
        log.error(f"Error reading or parsing frontmatter in {file_path}: {e}")
        return None

# --- ID Handling --- #

def ensure_id_in_file(file_path: Path, frontmatter: Dict[str, Any]) -> Tuple[Optional[str], bool]:
    """Checks for 'id' in frontmatter. If missing, generates one and writes it back to the file.
    Returns the ID and a boolean indicating if the file was modified.
    """
    if 'id' in frontmatter and frontmatter['id']:
        return str(frontmatter['id']), False # ID exists, file not modified

    new_id = str(uuid.uuid4())
    log.info(f"Generated new ID {new_id} for file: {file_path}")

    try:
        with open(file_path, 'r+', encoding='utf-8') as f:
            content = f.read()
            parts = content.split('---', 2)

            if len(parts) < 3:
                log.error(f"Cannot write ID: Malformed frontmatter structure in {file_path}")
                return None, False

            # Reconstruct frontmatter with the new ID
            current_fm = yaml.load(parts[1]) # Load existing FM again
            if not isinstance(current_fm, dict): current_fm = {}
            current_fm['id'] = new_id

            f.seek(0) # Go to the beginning of the file
            # Write the start delimiter, ensure a newline follows
            f.write("---\n") # <--- Explicitly add newline here
            # Use a temporary string buffer for dump to avoid writing directly to f
            import io
            string_stream = io.StringIO()
            yaml.dump(current_fm, string_stream)
            dumped_fm = string_stream.getvalue()
            # Remove potential leading/trailing whitespace added by dump if needed, but usually fine
            f.write(dumped_fm) # Write the dumped string
            # Ensure the frontmatter block ends with a newline before the closing delimiter
            if not dumped_fm.endswith('\n'):
                 f.write("\n")
            f.write("---")
            # Ensure body starts on a newline if not already present
            body_content = parts[2]
            if body_content and not body_content.startswith( ('\n', '\r') ):
                 f.write("\n")
            f.write(body_content) # Write the original body content
            f.truncate() # Remove any trailing content if the new content is shorter

        log.info(f"Successfully wrote new ID {new_id} to file: {file_path}")
        return new_id, True # Return new ID, indicate file was modified

    except (IOError, ScannerError, ParserError) as e:
        log.error(f"Error writing ID back to file {file_path}: {e}")
        return None, False
    except Exception as e:
        log.error(f"Unexpected error writing ID back to file {file_path}: {e}")
        return None, False

# --- Sync Logic --- #

def sync_file_to_db(file_path_str: str, db_conn: sqlite3.Connection, schema: Dict[str, str]):
    """Handles the synchronization of a single file to the database."""
    file_path = Path(file_path_str)
    if not file_path.is_file() or file_path.suffix.lower() != '.md':
        log.debug(f"Skipping non-markdown file or directory: {file_path}")
        return

    log.info(f"Processing file: {file_path}")
    frontmatter = parse_frontmatter(file_path)

    if frontmatter is None:
        log.warning(f"Skipping file due to frontmatter parsing error: {file_path}")
        return
    if not frontmatter:
        log.info(f"Skipping file with empty or no frontmatter: {file_path}")
        return

    # Ensure file has an ID, write back if needed
    person_id, modified = ensure_id_in_file(file_path, frontmatter)

    if not person_id:
        log.error(f"Failed to get or generate ID for file {file_path}. Skipping sync.")
        return

    # If the file was modified to add the ID, re-parse frontmatter to be safe
    # Although ensure_id_in_file updates the dict, the write might format differently
    if modified:
        log.info(f"Re-parsing frontmatter after adding ID for {file_path}")
        frontmatter = parse_frontmatter(file_path)
        if frontmatter is None or 'id' not in frontmatter:
            log.error(f"Failed to re-parse frontmatter after adding ID for {file_path}. Skipping sync.")
            return
        person_id = str(frontmatter['id']) # Ensure we use the ID from re-parse

    # Add/update filepath relative to the watched PEOPLE_DIR
    try:
        relative_path = file_path.relative_to(PEOPLE_DIR)
        frontmatter['filepath'] = str(relative_path).replace('\\', '/') # Use forward slashes
    except ValueError:
         log.warning(f"Could not determine relative path for {file_path} based on PEOPLE_DIR {PEOPLE_DIR}. Storing absolute path.")
         frontmatter['filepath'] = str(file_path)

    # Update the data dict with the confirmed ID
    frontmatter['id'] = person_id

    # Upsert data into the database
    upsert_person(db_conn, frontmatter, schema)


def delete_file_from_db(file_path_str: str, db_conn: sqlite3.Connection, schema: Dict[str, str]):
    """Handles deleting the database entry corresponding to a deleted file."""
    file_path = Path(file_path_str)
    relative_path_str = "<unknown>"
    try:
        relative_path = file_path.relative_to(PEOPLE_DIR)
        relative_path_str = str(relative_path).replace('\\', '/') # Use forward slashes
        log.info(f"Attempting deletion for file: {relative_path_str}")

        # Find the ID using the stored filepath
        person_id = get_id_by_filepath(db_conn, relative_path_str)

        if person_id:
            log.info(f"Found ID {person_id} for deleted file {relative_path_str}. Deleting from DB.")
            delete_person_by_id(db_conn, person_id)
        else:
            log.warning(f"Could not find database entry for deleted file: {relative_path_str}")

    except ValueError:
        log.warning(f"Could not determine relative path for deleted file {file_path} based on PEOPLE_DIR {PEOPLE_DIR}. Cannot determine ID.")
    except Exception as e:
        log.error(f"Error during deletion process for file {relative_path_str}: {e}")

# --- Initial Scan --- #

def initial_scan_and_sync(db_conn: sqlite3.Connection, schema: Dict[str, str]):
    """Performs an initial scan of the PEOPLE_DIR and reconciles with the database."""
    log.info("Starting initial scan and synchronization...")

    # 1. Get all Markdown files from disk
    try:
        all_md_files = list(PEOPLE_DIR.rglob('*.md'))
        log.info(f"Found {len(all_md_files)} Markdown files in {PEOPLE_DIR}.")
    except Exception as e:
        log.error(f"Error scanning directory {PEOPLE_DIR}: {e}")
        return # Cannot proceed without file list

    # 2. Get all IDs and filepaths from the database
    db_entries = {}
    try:
        cursor = db_conn.cursor()
        # Ensure filepath column exists before querying it
        cursor.execute("PRAGMA table_info(people)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'id' not in columns or 'filepath' not in columns:
             log.warning("Database table 'people' is missing 'id' or 'filepath' column. Skipping initial delete check.")
        else:
            cursor.execute("SELECT id, filepath FROM people")
            for row in cursor.fetchall():
                db_entries[row['id']] = row['filepath'] # Assumes id is unique
            log.info(f"Found {len(db_entries)} entries in the database.")
    except sqlite3.Error as e:
        log.error(f"Database error fetching existing entries: {e}")
        # Might still proceed with upserting files, but deletion check will be skipped

    # 3. Process files: Upsert to DB and track processed IDs
    processed_ids = set()
    for file_path in all_md_files:
        log.debug(f"Initial scan processing: {file_path}")
        try:
            # Use existing sync function, it handles ID generation and upsert
            # We pass the file path string
            sync_file_to_db(str(file_path), db_conn, schema)

            # After syncing, try to get the ID back from the file
            # (it might have been added by sync_file_to_db)
            final_frontmatter = parse_frontmatter(file_path)
            if final_frontmatter and 'id' in final_frontmatter:
                 processed_ids.add(final_frontmatter['id'])
            else:
                 log.warning(f"Could not determine final ID for {file_path} after sync during initial scan.")

        except Exception as e:
            log.error(f"Error during initial sync for file {file_path}: {e}", exc_info=True)

    # 4. Process deletions: Check DB IDs not found in the file scan
    if db_entries:
        db_ids = set(db_entries.keys())
        deleted_ids = db_ids - processed_ids
        if deleted_ids:
            log.info(f"Found {len(deleted_ids)} entries in DB whose files seem to be missing. Deleting...")
            for person_id in deleted_ids:
                 log.info(f"Deleting missing file record: ID {person_id} (associated path: {db_entries.get(person_id, '<unknown>')}) ")
                 try:
                    delete_person_by_id(db_conn, person_id)
                 except Exception as e:
                    log.error(f"Error deleting record with ID {person_id} during initial scan: {e}", exc_info=True)
        else:
            log.info("No missing file records detected in the database.")

    log.info("Initial scan and synchronization finished.") 