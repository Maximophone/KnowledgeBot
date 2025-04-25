import streamlit as st
import pandas as pd
import sqlite3
import logging
from pathlib import Path
import json

# Import configuration to get DB path
# from config import DB_PATH, SCHEMA # Old import
from config.config import DB_PATH, SCHEMA, PEOPLE_DIR # Corrected import, add PEOPLE_DIR for sidebar

# --- Configuration ---
TABLE_NAME = "people"

# Setup basic logging for the dashboard
# Update logger name for clarity
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - DASHBOARD - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# --- Database Connection ---
@st.cache_resource # Cache the connection across Streamlit reruns
def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """Establishes and returns a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        logging.info(f"Dashboard connected to database: {db_path}")
        # Set row factory to access columns by name
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logging.error(f"Dashboard database connection error: {e}")
        st.error(f"Failed to connect to database: {e}")
        return None

# --- Data Loading ---
@st.cache_data(ttl=60) # Cache data for 60 seconds
def load_data(_conn: sqlite3.Connection) -> pd.DataFrame:
    """Loads data from the people table into a pandas DataFrame."""
    if not _conn:
        return pd.DataFrame() # Return empty DataFrame if connection failed
    try:
        query = f"SELECT * FROM {TABLE_NAME}"
        df = pd.read_sql_query(query, _conn)
        logging.info(f"Loaded {len(df)} rows from table '{TABLE_NAME}'.")

        # Attempt to decode JSON strings for list columns
        for col, type_str in SCHEMA.items():
            if type_str.startswith("list[") and col in df.columns:
                try:
                    # Handle potential errors during JSON decoding
                    df[col] = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
                except Exception as json_e:
                    logging.warning(f"Could not decode JSON for column '{col}': {json_e}")
                    # Keep original data if decoding fails

        # Convert boolean (0/1) columns
        for col, type_str in SCHEMA.items():
             if type_str == "boolean" and col in df.columns:
                 # Ensure column is numeric first, handle potential errors
                 df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(bool)

        return df
    except pd.io.sql.DatabaseError as e:
        # Check if the error is due to the table not existing
        if "no such table" in str(e).lower():
            st.warning(f"Database table '{TABLE_NAME}' not found. Run the sync script first.")
            return pd.DataFrame()
        else:
             st.error(f"Database error loading data: {e}")
             return pd.DataFrame()
    except Exception as e:
        st.error(f"An unexpected error occurred loading data: {e}")
        return pd.DataFrame()

# --- Streamlit App Layout ---
st.set_page_config(page_title="Obsidian People Dashboard", layout="wide")
st.title("Obsidian People Database Dashboard")

st.write(f"Displaying data from: `{DB_PATH}`")

# Optional: Add a button to manually refresh data (Moved to top)
if st.button("Refresh Data"):
    st.cache_data.clear() # Clear the data cache
    st.cache_resource.clear() # Clear resource cache (like DB connection)
    st.rerun()

# Establish connection
conn = get_db_connection(DB_PATH)

if conn:
    # Load data
    df_people = load_data(conn)

    if not df_people.empty:
        st.info(f"Found {len(df_people)} entries.")
        # Display the main dataframe
        st.dataframe(df_people, use_container_width=True)

    else:
        st.warning("No data found in the database table.")

else:
    st.error("Could not establish database connection.")

# Add some basic info
st.sidebar.header("Info")
st.sidebar.write(f"Database: `{DB_PATH.name}`")
st.sidebar.write(f"Monitored Folder: `{PEOPLE_DIR}`") # Use imported PEOPLE_DIR 