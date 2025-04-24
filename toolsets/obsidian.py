from ai_core.tools import tool
from pathlib import Path
from config.paths import PATHS
from .file_utils import validate_filepath, ensure_md_extension, should_exclude
import os

# Directories to exclude from AI access
VAULT_EXCLUDE = [
    "AI Chats",      # AI conversation logs
    "AI Memory",     # AI memory system
    ".obsidian",     # Obsidian config
    ".smart-connections", # Plugin data
    ".trash",        # Deleted files
    ".git",          # Git data if vault is versioned
]

@tool(
    description="""Introduction to the Obsidian vault access system and navigation principles. This tool provides guidance on how to effectively explore and understand the interconnected notes in the vault.""",
    safe=True
)
def obsidian_system_introduction() -> str:
    return """OBSIDIAN VAULT ACCESS GUIDE

This toolset provides access to an Obsidian vault, which is a collection of interconnected markdown notes. Here are the key principles for effectively navigating and understanding the vault:

1. WIKILINKS - THE KEY TO NAVIGATION
   - Notes in Obsidian are connected through wikilinks, formatted as [[note name]]
   - When you see a wikilink in a note, you can follow it by using read_obsidian_note with the linked note's name
   - Example: If you see [[Project Ideas]], use read_obsidian_note("Project Ideas")
   - Some links might include an alias like [[note name|display text]] - use only the part before the |

2. EXPLORATION STRATEGIES
   - Start with list_obsidian_notes() to see available notes and directories at the root
   - Use list_obsidian_notes("directory") to explore specific directories
   - When reading a note, identify wikilinks and follow interesting connections
   - Build context by following relevant links rather than reading notes in isolation

3. SYSTEM BOUNDARIES
   - Some directories are excluded for privacy and system functionality
   - If a path is not accessible, you'll receive a clear error message
   - Focus on the content and connections available to you

4. BEST PRACTICES
   - Always check for wikilinks in notes you read
   - Use the directory structure to understand the organization of knowledge
   - Follow link chains when they're relevant to the user's query

Remember: The vault is a network of connected ideas. The best way to find relevant information is often to follow the natural connections between notes through their wikilinks."""
    
@tool(
    description="""Reads the contents of a specific note from the Obsidian vault. The note path should be relative to the vault root. 
    The tool returns both the raw content of the note and any frontmatter metadata if present. Some directories are excluded for privacy and system functionality.""",
    filepath="The path to the note relative to the vault root (e.g., 'folder/note.md')",
    safe=True
)
def read_obsidian_note(filepath: str) -> str:
    """Reads a note from the Obsidian vault"""
    # Validate filepath
    validate_filepath(filepath)
    filepath = ensure_md_extension(filepath)
    
    # Check if path is in excluded directories
    if should_exclude(filepath, VAULT_EXCLUDE):
        return f"Error: Access to {filepath} is not allowed"
    
    # Resolve the full path and check it's within allowed directory
    full_path = (PATHS.vault_path / filepath).resolve()
    try:
        full_path.relative_to(PATHS.vault_path)
    except ValueError:
        raise ValueError("Invalid filepath: attempted to read outside of vault")
    
    if not full_path.exists():
        return f"Error: Note {filepath} does not exist"
    
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return content

@tool(
    description="""Lists all notes and directories under a specified directory in the Obsidian vault, excluding certain system and private directories. 
    Returns a flat list of items in the specified directory. If no directory is specified, lists items at the vault root.""",
    directory="The directory path relative to the vault root (e.g., 'Projects' or 'Daily Notes'). If empty, shows contents of the vault root.",
    safe=True
)
def list_obsidian_notes(directory: str = "") -> str:
    """Lists notes and directories in the specified vault directory"""
    # Validate directory path if provided
    if directory:
        validate_filepath(directory)
        
        # Check if directory is in excluded list
        if should_exclude(directory, VAULT_EXCLUDE):
            return f"Error: Access to {directory} is not allowed"
    
    # Resolve the full path and check it's within allowed directory
    full_path = (PATHS.vault_path / directory).resolve()
    try:
        full_path.relative_to(PATHS.vault_path)
    except ValueError:
        raise ValueError("Invalid directory: attempted to list outside of vault")
    
    if not full_path.exists():
        return f"Error: Directory {directory} does not exist"
    
    if not full_path.is_dir():
        return f"Error: {directory} is not a directory"
    
    items = {'files': [], 'directories': []}
    
    # List all items in the specified directory
    for item in full_path.iterdir():
        # Skip excluded directories and files
        if should_exclude(item.name, VAULT_EXCLUDE):
            continue
            
        if item.is_file() and item.suffix == '.md':
            items['files'].append(item.name)
        elif item.is_dir() and not item.name.startswith('.'):
            items['directories'].append(item.name)
    
    # Sort both lists for consistency
    items['files'].sort()
    items['directories'].sort()
    
    return str(items)

@tool(
    description="""Reads the contents of multiple notes from the Obsidian vault simultaneously. Accepts a comma-separated list of filepaths relative to the vault root.
    Returns a dictionary mapping each filepath to its content. Invalid or inaccessible notes will return error messages in the dictionary.""",
    filepaths="Comma-separated list of paths to the notes relative to the vault root (e.g., 'folder/note1.md, folder/note2.md')",
    safe=True
)
def read_multiple_obsidian_notes(filepaths: str) -> str:
    """Reads multiple notes from the Obsidian vault"""
    # Parse the comma-separated string into a list
    filepath_list = [f.strip() for f in filepaths.split(',')]
    results = {}
    
    for filepath in filepath_list:
        try:
            # Reuse existing read_obsidian_note logic
            content = read_obsidian_note(filepath)
            results[filepath] = content
        except Exception as e:
            results[filepath] = f"Error reading {filepath}: {str(e)}"
    
    return str(results)  # Convert dictionary to string for return

# Export the tools
TOOLS = [
    obsidian_system_introduction,
    read_obsidian_note,
    list_obsidian_notes,
    read_multiple_obsidian_notes
] 