import yaml
import os
import sys
import logging
from pathlib import Path

# Setup basic logging for config loading issues
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - CONFIG - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# --- Configuration Settings ---

# Get the directory where this config script is located
_config_dir = Path(__file__).parent.resolve()
logging.debug(f"Config directory (_config_dir): {_config_dir}")

# Get the root directory of the obsidian_sync project (one level up from config)
_project_root = _config_dir.parent.resolve()
logging.debug(f"Project root (_project_root): {_project_root}")


def get_default_people_dir() -> Path:
    """
    Get the default People directory based on the operating system.
    Can be overridden by the OBSIDIAN_PEOPLE_DIR environment variable.
    """
    if sys.platform == "darwin":  # macOS
        home = Path.home()
        # Try newer Google Drive location first
        cloud_storage = home / "Library" / "CloudStorage"
        if cloud_storage.exists():
            gdrive_folders = list(cloud_storage.glob("GoogleDrive-*"))
            if gdrive_folders:
                return gdrive_folders[0] / "My Drive" / "Obsidian" / "People"
        # Try older Google Drive location
        old_gdrive = home / "Google Drive" / "Obsidian" / "People"
        if old_gdrive.exists():
            return old_gdrive
        # Default fallback for macOS
        return cloud_storage / "GoogleDrive" / "My Drive" / "Obsidian" / "People"
    
    elif sys.platform == "win32":  # Windows
        # Check for common Windows paths
        for drive_letter in ["G", "H", "I", "D", "E"]:
            people_dir = Path(f"{drive_letter}:/My Drive/Obsidian/People")
            if people_dir.exists():
                return people_dir
        # Default fallback for Windows
        return Path("G:/My Drive/Obsidian/People")
    
    else:  # Linux and others
        home = Path.home()
        return home / "Obsidian" / "People"


# --- Paths ---
# Use environment variable if set, otherwise use platform-appropriate default
PEOPLE_DIR_STR = os.environ.get("OBSIDIAN_PEOPLE_DIR")
if PEOPLE_DIR_STR:
    PEOPLE_DIR = Path(PEOPLE_DIR_STR)
else:
    PEOPLE_DIR = get_default_people_dir()

# Path to the schema definition file (relative to this config file's directory)
SCHEMA_PATH = _config_dir / "schema.yaml"

# Path to the SQLite database file
# Place it in a 'data' subdirectory within the obsidian_sync project root
DB_PATH = _project_root / "data" / "people.db"

# --- Schema Loading ---

def load_schema(schema_path: Path = SCHEMA_PATH) -> dict:
    """Loads the schema definition from the YAML file."""
    logging.info(f"Attempting to load schema from: {schema_path}")
    if not schema_path.exists():
        logging.error(f"Schema file not found at: {schema_path}")
        raise FileNotFoundError(f"Schema file not found at: {schema_path}")
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Error reading schema file {schema_path}: {e}")
        raise

    if not schema or 'fields' not in schema:
        logging.error(f"Invalid schema format in {schema_path}. Expected a 'fields' key.")
        raise ValueError(f"Invalid schema format in {schema_path}. Expected a 'fields' key.")
    # Basic validation (ensure it's a dictionary)
    if not isinstance(schema['fields'], dict):
         logging.error(f"Invalid schema format in {schema_path}. 'fields' should be a dictionary.")
         raise ValueError(f"Invalid schema format in {schema_path}. 'fields' should be a dictionary.")
    logging.info(f"Schema loaded successfully from {schema_path}.")
    return schema['fields']

# --- Helper Functions ---

def ensure_dirs():
    """Ensure necessary directories exist (like the data directory)."""
    try:
        logging.info(f"Ensuring data directory exists: {DB_PATH.parent}")
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logging.error(f"Failed to create data directory {DB_PATH.parent}: {e}")
        # Depending on severity, you might want to raise this or exit

    if not PEOPLE_DIR.exists() or not PEOPLE_DIR.is_dir():
        logging.warning(f"Configured PEOPLE_DIR '{PEOPLE_DIR}' does not exist or is not a directory.")
        logging.warning("Please ensure the path is correct and accessible.")
        logging.warning("You can set the OBSIDIAN_PEOPLE_DIR environment variable to override.")

# --- Load Schema on Import ---
SCHEMA = {}
try:
    SCHEMA = load_schema()
except (FileNotFoundError, ValueError, OSError, Exception) as e:
    logging.error(f"Failed to load schema during import: {e}")
    # SCHEMA remains empty, main script should check and exit

# --- Ensure directories exist on import ---
ensure_dirs()

logging.info(f"Final Configuration Paths:")
logging.info(f"  People Directory: {PEOPLE_DIR}")
logging.info(f"  Schema Path: {SCHEMA_PATH}")
logging.info(f"  Database Path: {DB_PATH}")
