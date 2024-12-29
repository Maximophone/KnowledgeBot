from ..tools import tool
from pathlib import Path
from config.paths import PATHS
from processors.common.frontmatter import parse_frontmatter, frontmatter_to_text, update_frontmatter
from datetime import datetime
import json
import os

def ensure_md_extension(filename: str) -> str:
    """Ensures the filename has a .md extension"""
    if not filename.endswith('.md'):
        filename += '.md'
    return filename

def create_wikilink(text: str) -> str:
    """Converts text to a valid wikilink format [[text]]"""
    return f"[[{text}]]"

def validate_filepath(filepath: str) -> None:
    if not filepath or '..' in filepath or filepath.startswith('/') or filepath.startswith('\\'):
        raise ValueError("Invalid filepath: must not contain '..' or start with '/' or '\\'")
    
    # Check for empty or whitespace-only names
    if not filepath.strip():
        raise ValueError("Filepath cannot be empty or whitespace")
    
    # Check for reserved Windows names
    WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                       'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3',
                       'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
    name_without_ext = os.path.splitext(os.path.basename(filepath))[0].upper()
    if name_without_ext in WINDOWS_RESERVED:
        raise ValueError(f"Invalid filepath: {name_without_ext} is a reserved name")
    
    # Block hidden files
    if filepath.startswith('.'):
        raise ValueError("Hidden files are not allowed")
    
    # Allow only safe characters
    safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./')
    invalid_chars = [c for c in filepath if c not in safe_chars]
    if invalid_chars:
        raise ValueError(f"Filepath contains invalid characters: {', '.join(repr(c) for c in invalid_chars)}")

@tool(
    description="""CRITICAL: ALWAYS READ _MEMORY_SYSTEM_GUIDE.md FIRST (with the read_memory tool)!

This is a system introduction for me (the AI) about my internal memory toolset. These tools provide me with a persistent memory system that is STRICTLY FOR MY INTERNAL USE ONLY. Users cannot and should not directly access these files - I must always share relevant information directly in conversation responses.

The memory system is governed by a structured guide (_MEMORY_SYSTEM_GUIDE.md) that is the foundational document I must consult at the start of every session. This guide defines critical principles including:
1. The internal-only nature of this system
2. How to properly share information with users
3. Organization and naming conventions
4. Best practices for memory management

Following this guide ensures I maintain consistency and effectiveness in managing my knowledge base while maintaining appropriate boundaries between my internal processes and user interactions.""",
    safe=True
)
def system_introduction() -> str:
    return ""

@tool(
    description="""Allows me (the AI) to store new information or update existing knowledge in my persistent memory system. I can organize information in directories (e.g., 'concepts/physics.md') and create connections between related memories using wikilinks ([[filename]]). Files are automatically timestamped and can include metadata. This is my way to maintain knowledge across conversations, but I will always share relevant information directly in our discussion rather than expecting you to access these files.""",
    filepath="The path to the file relative to the memory root (e.g., 'concepts/physics.md' or 'daily/today-thoughts.md')",
    content="The markdown content to write to the file. Can include wikilinks using [[filename]] syntax",
    metadata="Optional JSON string of frontmatter metadata to include at the top of the file",
    append="If True, appends content to existing file instead of overwriting. Defaults to False",
    safe=True
)
def write_memory(
    filepath: str,
    content: str,
    metadata: str = None,
    append: bool = False
) -> str:
    """Writes or updates a markdown file in the memory system"""
    # Validate filepath
    validate_filepath(filepath)
    filepath = ensure_md_extension(filepath)
    
    # Resolve the full path and check it's within allowed directory
    full_path = (PATHS.ai_memory / filepath).resolve()
    try:
        full_path.relative_to(PATHS.ai_memory)
    except ValueError:
        raise ValueError("Invalid filepath: attempted to write outside of allowed directory")
    
    # Create parent directories if they don't exist
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Prepare metadata
    meta = {} if metadata is None else json.loads(metadata)
    meta['last_updated'] = datetime.now().isoformat()
    
    if append and full_path.exists():
        # Read existing content and metadata
        with open(full_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        existing_meta = parse_frontmatter(existing_content) or {}
        # Remove frontmatter from content if it exists
        if existing_content.startswith('---\n'):
            content_parts = existing_content.split('---\n', 2)
            if len(content_parts) >= 3:
                existing_content = content_parts[2]
        # Merge metadata and append content
        meta = {**existing_meta, **meta}
        content = f"{existing_content}\n\n{content}"
    
    # Create the full document with frontmatter
    full_content = frontmatter_to_text(meta) + content
    
    # Write the file
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    return f"Successfully wrote to {filepath}"

@tool(
    description="""Enables me to retrieve information I've previously stored in my memory system. I can access both the content and metadata of specific files I've stored. When you ask about something I've memorized, I'll read it and share the relevant information directly in our conversation rather than expecting you to access these files.""",
    filepath="The path to the file relative to the memory root (e.g., 'concepts/physics.md')",
    safe=True
)
def read_memory(filepath: str) -> str:
    """Reads a markdown file from the memory system"""
    # Validate filepath
    validate_filepath(filepath)
    filepath = ensure_md_extension(filepath)
    
    # Resolve the full path and check it's within allowed directory
    full_path = (PATHS.ai_memory / filepath).resolve()
    try:
        full_path.relative_to(PATHS.ai_memory)
    except ValueError:
        raise ValueError("Invalid filepath: attempted to read outside of allowed directory")
    
    if not full_path.exists():
        return f"Error: File {filepath} does not exist"
    
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    metadata = parse_frontmatter(content) or {}
    
    # Remove frontmatter from content if it exists
    if content.startswith('---\n'):
        content_parts = content.split('---\n', 2)
        if len(content_parts) >= 3:
            content = content_parts[2]
    
    return json.dumps({
        'metadata': metadata,
        'content': content
    })

@tool(
    description="""Shows me what information I have stored in a specific directory of my memory system. This helps me navigate my own knowledge structure through files and subdirectories. When you ask about what I remember about a particular topic, I'll use this to check my available memories and share the relevant information directly with you.""",
    directory="The directory path relative to the memory root (e.g., 'concepts' or 'daily')",
    safe=True
)
def list_memories(directory: str = "") -> str:
    """Lists all files in a memory directory"""
    # Validate directory path
    if directory:  # Only validate if directory is not empty
        validate_filepath(directory)
    
    # Resolve the full path and check it's within allowed directory
    full_path = (PATHS.ai_memory / directory).resolve()
    try:
        full_path.relative_to(PATHS.ai_memory)
    except ValueError:
        raise ValueError("Invalid directory: attempted to list outside of allowed directory")
    
    if not full_path.exists():
        return f"Error: Directory {directory} does not exist"
    
    # Get all files and directories
    items = {}
    for item in full_path.iterdir():
        if item.is_file() and item.suffix == '.md':
            items[item.name] = "file"
        elif item.is_dir():
            items[item.name] = "directory"
    
    return json.dumps(items)

@tool(
    description="""Allows me to search across my entire memory system for specific information, looking through both content and metadata. This helps me find relevant information I've stored even if I don't remember exactly where it is. When you ask about a topic, I can search my memories and share the relevant findings directly in our conversation.""",
    query="The search term to look for in files",
    safe=True
)
def search_memories(query: str) -> str:
    """Searches through all memory files for specific content"""
    results = []
    
    for filepath in PATHS.ai_memory.rglob('*.md'):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata = parse_frontmatter(content) or {}
            
            # Remove frontmatter from content if it exists
            if content.startswith('---\n'):
                content_parts = content.split('---\n', 2)
                if len(content_parts) >= 3:
                    content = content_parts[2]
            
            relative_path = filepath.relative_to(PATHS.ai_memory)
            
            # Search in content
            if query.lower() in content.lower():
                results.append({
                    'file': str(relative_path),
                    'type': 'content',
                    'excerpt': find_excerpt(content, query)
                })
            
            # Search in metadata
            meta_str = json.dumps(metadata).lower()
            if query.lower() in meta_str:
                results.append({
                    'file': str(relative_path),
                    'type': 'metadata',
                    'metadata': metadata
                })
        except Exception as e:
            continue
    
    return json.dumps(results)

def find_excerpt(content: str, query: str, context_chars: int = 100) -> str:
    """Helper function to find and return an excerpt of text around a query"""
    idx = content.lower().find(query.lower())
    if idx == -1:
        return ""
    
    start = max(0, idx - context_chars)
    end = min(len(content), idx + len(query) + context_chars)
    
    excerpt = content[start:end]
    if start > 0:
        excerpt = f"...{excerpt}"
    if end < len(content):
        excerpt = f"{excerpt}..."
    
    return excerpt

# Export the tools
TOOLS = [
    system_introduction,
    write_memory,
    read_memory,
    list_memories,
    # search_memories # Deactivated as it's not very useful
]
