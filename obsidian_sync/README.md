# Obsidian People Sync & Dashboard

This project provides a background service to synchronize YAML frontmatter from Markdown notes in a specified Obsidian directory (intended for notes about people) to a SQLite database. It also includes a simple Streamlit-based web dashboard to view the synchronized data.

---

## For Users

### What it Does

*   **Monitors:** Watches a designated folder in your Obsidian vault (e.g., `People`) for changes to Markdown (`.md`) files.
*   **Parses:** Reads the YAML frontmatter section of created or modified notes.
*   **Generates IDs:** If a note doesn't have a unique `id` field in its frontmatter, the script generates a UUID and writes it back into the file.
*   **Synchronizes:** Creates or updates a corresponding row in a SQLite database (`people.db`) based on the fields defined in the schema (`config/schema.yaml`). Lists are stored as JSON strings, booleans as 0/1 integers.
*   **Handles Deletions:** Removes the corresponding row from the database when a monitored Markdown file is deleted.
*   **Initial Scan:** Performs a full scan of the directory on startup to sync existing files and remove database entries for files deleted while the script was offline.
*   **Dashboard:** Provides a web interface (`dashboard.py` run via Streamlit) to view the contents of the synchronized database table.

### Installation

1.  **Clone/Download:** Make sure you have this `obsidian_sync` project directory.
2.  **Navigate:** Open your terminal (like Git Bash, CMD, PowerShell) and navigate into the project directory:
    ```bash
    cd path/to/knowledgebot/obsidian_sync
    ```
3.  **Create Virtual Environment:** Create a Python virtual environment to isolate dependencies:
    ```bash
    python -m venv .venv
    ```
4.  **Activate Virtual Environment:**
    *   **Git Bash / Linux / macOS:** `source .venv/Scripts/activate` (or `source .venv/bin/activate` on Linux/macOS)
    *   **Windows CMD:** `.venv\Scripts\activate.bat`
    *   **Windows PowerShell:** `.venv\Scripts\Activate.ps1` (You might need to adjust script execution policy: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`)
    *   *(Your terminal prompt should now show `(.venv)`)*
5.  **Install Dependencies:** Install the required Python packages:
    ```bash
    python -m pip install -r requirements.txt
    ```

### Configuration

*   **Main Configuration:** The most important setting is the path to your Obsidian directory containing the 'People' notes.
    *   Open the `obsidian_sync/config/config.py` file.
    *   Locate the `DEFAULT_PEOPLE_DIR` variable and change its value if `G:/My Drive/Obsidian/People` is not correct for your setup.
    *   Alternatively, you can set the `OBSIDIAN_PEOPLE_DIR` environment variable before running the script.
*   **Schema:** The fields synchronized are defined in `obsidian_sync/config/schema.yaml`. You can modify this if your frontmatter structure changes, but be aware that removing fields might require manual database adjustments if you want to remove the corresponding columns.

### Running the Sync Service & Dashboard

1.  **Activate Environment:** Make sure your virtual environment is activated (see step 4 in Installation).
2.  **Run:** Execute the wrapper script from within the `obsidian_sync` directory:
    ```bash
    python run_all.py
    ```
3.  **Output:**
    *   You will see logs in the terminal indicating the sync script (`main.py`) has started and is watching the configured directory.
    *   The Streamlit dashboard should automatically open in your default web browser.
    *   The initial scan might take a few moments depending on the number of files.
4.  **Stopping:** Press `Ctrl+C` in the terminal where `run_all.py` is running. This will attempt to gracefully stop both the sync script and the dashboard server.

### Database Location

The SQLite database file is created at `obsidian_sync/data/people.db`.

You can inspect this file using tools like [DB Browser for SQLite](https://sqlitebrowser.org/).

### Troubleshooting

*   **Schema Not Found / Incorrect Paths:** Double-check that `config.py` is inside the `config` subdirectory and that `schema.yaml` is also there. Ensure the paths printed during startup in the logs look correct.
*   **Sync Not Happening:** Check the terminal logs from `run_all.py` for errors from the `MAIN` or `SYNC` components. Ensure the `PEOPLE_DIR` in `config.py` is correct and accessible.
*   **Dashboard Errors:** Check the terminal logs for errors from the `DASHBOARD` component. Ensure the database file exists and the table `people` has been created (this happens on the first successful run of the sync script).
*   **Permissions (PowerShell):** If activation fails in PowerShell, you might need to allow script execution for the current process: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`

---

## For Developers

### Project Structure

*   `config/`: Contains configuration files.
    *   `config.py`: Loads settings, defines paths (People dir, DB path, Schema path), loads schema.
    *   `schema.yaml`: Defines the expected fields and types in the Markdown frontmatter.
*   `data/`: Default location for the generated SQLite database (`people.db`). (Created automatically).
*   `.venv/`: Python virtual environment (Created by user).
*   `database.py`: Handles all SQLite database interactions (connection, table creation/altering, upserts, deletes).
*   `sync.py`: Contains the core logic for parsing frontmatter, handling the `id` field (generation and write-back), performing the initial scan, and defining the main sync/delete operations triggered by file events.
*   `main.py`: Sets up `watchdog` file system observer, initializes the database connection, runs the initial scan, and triggers sync/delete operations based on file events.
*   `dashboard.py`: A Streamlit application to display data from the database.
*   `run_all.py`: A wrapper script using `subprocess` to launch `main.py` and the Streamlit `dashboard.py` concurrently and manage their shutdown.
*   `requirements.txt`: Lists Python package dependencies.
*   `README.md`: This file.

### Key Libraries

*   `watchdog`: Monitors file system events.
*   `ruamel.yaml`: Parses and writes YAML frontmatter, attempting to preserve formatting and comments.
*   `sqlite3`: Python's built-in library for SQLite database interaction.
*   `streamlit`: Used to create the web dashboard.
*   `pandas`: Used by Streamlit for efficient data handling and display.
*   `uuid`: Generates unique IDs for new notes.

### Core Logic Overview

1.  **Startup (`run_all.py` -> `main.py`):**
    *   Load configuration (`config.config`).
    *   Initialize database connection (`database.initialize_database`), create/alter table based on `schema.yaml`.
    *   Perform initial scan (`sync.initial_scan_and_sync`):
        *   Scan all `.md` files in `PEOPLE_DIR`.
        *   Scan all `id`, `filepath` from DB.
        *   Call `sync.sync_file_to_db` for each file found.
        *   Compare DB IDs with IDs found/generated during file scan; delete orphaned DB entries.
    *   Start `watchdog` observer.
2.  **Event Handling (`main.py` -> `PeopleEventHandler`):
    *   `on_created`/`on_modified`: Trigger `sync.sync_file_to_db`.
    *   `on_deleted`: Trigger `sync.delete_file_from_db`.
    *   `on_moved`: Triggers both delete (for source) and sync (for destination).
3.  **Sync (`sync.sync_file_to_db`):
    *   Parse frontmatter.
    *   Check for `id`; if missing, generate UUID and call `sync.ensure_id_in_file` to write it back to the `.md` file.
    *   Re-parse frontmatter if ID was added.
    *   Calculate relative `filepath`.
    *   Call `database.upsert_person` to insert/update the DB record.
4.  **Delete (`sync.delete_file_from_db`):
    *   Calculate relative `filepath`.
    *   Find the corresponding `id` using `database.get_id_by_filepath`.
    *   Call `database.delete_person_by_id`.
5.  **Dashboard (`dashboard.py`):
    *   Connects to the DB.
    *   Loads data into a Pandas DataFrame.
    *   Displays the DataFrame using `st.dataframe`.

### Potential Future Enhancements

*   **Debouncing:** Add a delay/debounce mechanism to `PeopleEventHandler` to handle rapid file saves more gracefully (e.g., only process a file after a short period of no modifications).
*   **Error Handling:** More specific error handling and potential retry mechanisms for DB operations or file access.
*   **Configuration:** More robust configuration loading (e.g., dedicated config file format, better environment variable handling).
*   **Bidirectional Sync:** Implementing reliable DB -> File sync is complex (conflict resolution, triggering) and currently not supported.
*   **Schema Migrations:** More sophisticated handling of schema changes (renaming/deleting columns).
*   **Dashboard Features:** Add filtering, searching, sorting, and better display options to the dashboard.
*   **Logging:** More configurable logging levels and output options. 