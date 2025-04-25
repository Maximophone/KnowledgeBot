import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# --- Type Mapping ---

def get_sqlite_type(schema_type: str) -> str:
    """Maps schema type string to SQLite data type."""
    schema_type = schema_type.lower().strip()
    if schema_type == "string" or schema_type.startswith("list[") or schema_type == "date":
        # Store lists, dates, and regular strings as TEXT
        # Lists will be JSON encoded
        return "TEXT"
    elif schema_type == "boolean":
        return "INTEGER" # SQLite uses 0/1 for booleans
    elif schema_type == "integer":
        return "INTEGER"
    elif schema_type == "float" or schema_type == "number":
        return "REAL"
    else:
        logging.warning(f"Unsupported schema type '{schema_type}', defaulting to TEXT.")
        return "TEXT"

# --- Database Initialization ---

def initialize_database(db_path: Path, schema: Dict[str, str], table_name: str = "people") -> Optional[sqlite3.Connection]:
    """
    Initializes the SQLite database.
    Creates the table if it doesn't exist.
    Adds missing columns based on the schema if the table already exists.
    Returns the database connection or None if connection fails.
    """
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False) # Allow connection usage from different threads (watchdog)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        logging.info(f"Successfully connected to database: {db_path}")

        # Get existing columns if table exists
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        if not existing_columns:
            # Table doesn't exist, create it
            column_defs = []
            for field, type_str in schema.items():
                sqlite_type = get_sqlite_type(type_str)
                if field == 'id':
                    column_defs.append(f"'{field}' {sqlite_type} PRIMARY KEY")
                else:
                    column_defs.append(f"'{field}' {sqlite_type}")
            create_table_sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"
            logging.info(f"Creating table '{table_name}' with SQL: {create_table_sql}")
            cursor.execute(create_table_sql)
            conn.commit()
            logging.info(f"Table '{table_name}' created successfully.")
        else:
            # Table exists, check for missing columns
            logging.info(f"Table '{table_name}' already exists. Checking for schema updates...")
            missing_columns = schema.keys() - existing_columns
            if missing_columns:
                for field in missing_columns:
                    sqlite_type = get_sqlite_type(schema[field])
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN '{field}' {sqlite_type}"
                    logging.info(f"Adding missing column '{field}' with SQL: {alter_sql}")
                    try:
                        cursor.execute(alter_sql)
                    except sqlite3.OperationalError as e:
                         logging.error(f"Failed to add column '{field}': {e}. This might happen with unsupported ALTER TABLE operations in older SQLite versions.")
                conn.commit()
                logging.info(f"Added missing columns: {', '.join(missing_columns)}")
            else:
                logging.info("Schema is up-to-date.")

        return conn
    except sqlite3.Error as e:
        logging.error(f"Database error during initialization: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during database initialization: {e}")
        return None


# --- Data Transformation ---

def _prepare_value_for_db(value: Any, schema_type: str) -> Any:
    """Prepares a Python value for insertion into SQLite based on schema type."""
    schema_type = schema_type.lower().strip()
    if value is None:
        return None
    if schema_type.startswith("list["):
        if isinstance(value, list):
            return json.dumps(value) # Store lists as JSON strings
        elif value == '': # Handle empty string from frontmatter for lists
             return json.dumps([])
        else:
            logging.warning(f"Expected a list for type {schema_type}, got {type(value)}. Storing as is.")
            return str(value) # Fallback
    elif schema_type == "boolean":
        # Explicitly handle common string representations of boolean
        if isinstance(value, str):
            val_lower = value.lower()
            if val_lower in ['true', 'yes', 'on', '1']:
                return 1
            elif val_lower in ['false', 'no', 'off', '0']:
                return 0
        # Handle actual boolean/integer types
        return 1 if bool(value) else 0
    # For other types (string, date, integer, real), SQLite handles them directly
    # or they are stored as TEXT anyway.
    return value


# --- Database Operations ---

def upsert_person(conn: sqlite3.Connection, data: Dict[str, Any], schema: Dict[str, str], table_name: str = "people"):
    """Inserts or updates a person record in the database based on the 'id' field."""
    if 'id' not in data or not data['id']:
        logging.error("Cannot upsert record: 'id' is missing or empty in data.")
        return

    person_id = data['id']
    cursor = conn.cursor()

    # Prepare data: filter based on schema and convert types
    db_data = {}
    for field, type_str in schema.items():
        if field in data:
             db_data[field] = _prepare_value_for_db(data[field], type_str)
        else:
            db_data[field] = None # Ensure all schema fields are present, use NULL if missing

    columns = list(db_data.keys())
    placeholders = [f":{col}" for col in columns]
    update_setters = [f"'{col}' = :{col}" for col in columns if col != 'id'] # Don't update id

    # Use INSERT OR REPLACE (UPSERT) - requires SQLite 3.24+
    # Alternatively, could check existence first, then INSERT or UPDATE
    sql = f"""
    INSERT INTO {table_name} ({', '.join([f"'{c}'" for c in columns])})
    VALUES ({', '.join(placeholders)})
    ON CONFLICT(id) DO UPDATE SET
    {', '.join(update_setters)}
    """

    try:
        # logging.debug(f"Executing UPSERT SQL: {sql} with data: {db_data}")
        cursor.execute(sql, db_data)
        conn.commit()
        logging.info(f"Successfully upserted record with id: {person_id}")
    except sqlite3.Error as e:
        logging.error(f"Database error during upsert for id {person_id}: {e}")
        conn.rollback() # Rollback transaction on error
    except Exception as e:
        logging.error(f"An unexpected error occurred during upsert for id {person_id}: {e}")
        conn.rollback()

def delete_person_by_id(conn: sqlite3.Connection, person_id: str, table_name: str = "people"):
    """Deletes a person record from the database based on the ID."""
    if not person_id:
        logging.warning("Attempted to delete record with empty ID.")
        return

    cursor = conn.cursor()
    sql = f"DELETE FROM {table_name} WHERE id = ?"
    try:
        # logging.debug(f"Executing DELETE SQL: {sql} with id: {person_id}")
        cursor.execute(sql, (person_id,))
        conn.commit()
        if cursor.rowcount > 0:
            logging.info(f"Successfully deleted record with id: {person_id}")
        else:
            logging.warning(f"Attempted to delete non-existent record with id: {person_id}")
    except sqlite3.Error as e:
        logging.error(f"Database error during delete for id {person_id}: {e}")
        conn.rollback()
    except Exception as e:
        logging.error(f"An unexpected error occurred during delete for id {person_id}: {e}")
        conn.rollback()

# --- Utility (Optional) ---
def get_id_by_filepath(conn: sqlite3.Connection, filepath: str, table_name: str = "people") -> Optional[str]:
    """Retrieves the ID associated with a specific filepath."""
    if 'filepath' not in [c[1] for c in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]:
         logging.warning("Cannot get ID by filepath: 'filepath' column does not exist in the table.")
         return None

    cursor = conn.cursor()
    sql = f"SELECT id FROM {table_name} WHERE filepath = ?"
    try:
        cursor.execute(sql, (filepath,))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        logging.error(f"Database error retrieving ID for filepath {filepath}: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred retrieving ID for filepath {filepath}: {e}")
        return None 