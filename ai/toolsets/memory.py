from ..tools import tool
from pathlib import Path
from config.paths import PATHS
from processors.common.frontmatter import parse_frontmatter, frontmatter_to_text, update_frontmatter
from datetime import datetime
from ..file_utils import validate_filepath, ensure_md_extension
import json
import os
from patch_ng import fromstring
import tempfile
import logging
from io import StringIO

def create_wikilink(text: str) -> str:
    """Converts text to a valid wikilink format [[text]]"""
    return f"[[{text}]]"

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
def memory_system_introduction() -> str:
    return ""

@tool(
    description="""Allows me (the AI) to create a new memory file. Will fail if the file already exists. This ensures memories are never accidentally overwritten. Use patch_memory to modify existing content or append_memory to add content at the end.""",
    filepath="The path to the file relative to the memory root (e.g., 'concepts/physics.md')",
    content="The markdown content to write to the file. Can include wikilinks using [[filename]] syntax",
    metadata="Optional JSON string of frontmatter metadata to include at the top of the file",
    safe=True
)
def create_memory(
    filepath: str,
    content: str,
    metadata: str = None
) -> str:
    """Creates a new markdown file in the memory system, fails if file exists"""
    # Validate filepath
    validate_filepath(filepath)
    filepath = ensure_md_extension(filepath)
    
    # Resolve the full path and check it's within allowed directory
    full_path = (PATHS.ai_memory / filepath).resolve()
    try:
        full_path.relative_to(PATHS.ai_memory)
    except ValueError:
        raise ValueError("Invalid filepath: attempted to write outside of allowed directory")
    
    # Fail if file already exists
    if full_path.exists():
        return f"Error: File {filepath} already exists. Use patch_memory to modify existing content or append_memory to add content at the end."
    
    # Create parent directories if they don't exist
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Prepare metadata
    meta = {} if metadata is None else json.loads(metadata)
    meta['last_updated'] = datetime.now().isoformat()
    
    # Create the full document with frontmatter
    full_content = frontmatter_to_text(meta) + content
    
    # Write the file
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    return f"Successfully created new file {filepath}"

@tool(
    description="""Allows me to add new content to the end of an existing memory file without overwriting previous content. This is useful for accumulating information over time while preserving the existing content. The new content will be separated from existing content with a newline. Files are automatically timestamped and can include updated metadata.""",
    filepath="The path to the file relative to the memory root (e.g., 'concepts/physics.md' or 'daily/today-thoughts.md')",
    content="The markdown content to append to the file. Can include wikilinks using [[filename]] syntax",
    metadata="Optional JSON string of frontmatter metadata to update at the top of the file",
    safe=True
)
def append_memory(
    filepath: str,
    content: str,
    metadata: str = None
) -> str:
    """Appends content to an existing markdown file in the memory system"""
    # Validate filepath
    validate_filepath(filepath)
    filepath = ensure_md_extension(filepath)
    
    # Resolve the full path and check it's within allowed directory
    full_path = (PATHS.ai_memory / filepath).resolve()
    try:
        full_path.relative_to(PATHS.ai_memory)
    except ValueError:
        raise ValueError("Invalid filepath: attempted to write outside of allowed directory")
    
    if not full_path.exists():
        return f"Error: File {filepath} does not exist. Use create_memory to create a new file."
    
    # Read existing content
    with open(full_path, 'r', encoding='utf-8') as f:
        existing_content = f.read()
    
    # Parse existing metadata
    existing_meta = parse_frontmatter(existing_content) or {}
    
    # Update metadata if provided
    if metadata:
        new_meta = json.loads(metadata)
        existing_meta.update(new_meta)
    
    # Always update timestamp
    existing_meta['last_updated'] = datetime.now().isoformat()
    
    # Get existing content without frontmatter
    if existing_content.startswith('---\n'):
        content_parts = existing_content.split('---\n', 2)
        if len(content_parts) >= 3:
            existing_content = content_parts[2]
    
    # Combine content with double newline separator
    full_content = frontmatter_to_text(existing_meta) + existing_content.rstrip() + '\n\n' + content
    
    # Write the updated file
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    return f"Successfully appended content to {filepath}"

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
    description="""Shows me the complete directory tree structure starting from a given directory in my memory system, including all files and subdirectories recursively. This helps me understand the full organization of my knowledge by seeing the entire hierarchy of files and folders. When you ask about what information I have on a topic, I can explore the complete structure under relevant directories to find and share all related memories.""",
    directory="The directory path relative to the memory root (e.g., 'concepts' or 'daily'). If empty, shows the complete memory tree.",
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
    
    # Get all files and directories recursively
    def build_tree(path):
        tree = {}
        for item in path.iterdir():
            if item.is_file() and item.suffix == '.md':
                tree[item.name] = "file"
            elif item.is_dir():
                tree[item.name] = build_tree(item)
        return tree
    
    tree = build_tree(full_path)
    return json.dumps(tree)

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

def apply_content_patch(filepath: Path, diff_content: str) -> tuple[bool, str, dict]:
    """
    Applies a patch to the content portion of a file, preserving frontmatter.
    
    Args:
        filepath: Path object pointing to the file to patch
        diff_content: The unified diff string to apply
        
    Returns:
        tuple of:
            - success: bool indicating if patch was successful
            - content: the new content (without frontmatter) or error message
            - metadata: the preserved metadata dictionary
    """
    # Set up logging capture
    log_capture = StringIO()
    log_handler = logging.StreamHandler(log_capture)
    patch_logger = logging.getLogger('patch_ng')
    patch_logger.addHandler(log_handler)
    patch_logger.setLevel(logging.WARNING)  # Capture WARNING and ERROR

    # Read the file
    with open(filepath, 'r', encoding='utf-8') as f:
        full_content = f.read()
    
    # Split frontmatter and content
    meta = parse_frontmatter(full_content) or {}
    content_start = full_content.find('---\n', 4) + 4 if full_content.startswith('---\n') else 0
    content = full_content[content_start:]
    
    # Create a temporary file with just the content
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.md', delete=False) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name
    
    try:
        # Adjust the diff to use the temp file path
        lines = diff_content.split('\n')
        adjusted_lines = []
        for line in lines:
            if line.startswith('---') or line.startswith('+++'):
                # Replace the filepath with the temp file path
                prefix = line[:4]  # '---' or '+++'
                adjusted_lines.append(f"{prefix} {temp_path}")
            else:
                adjusted_lines.append(line)
        adjusted_diff = '\n'.join(adjusted_lines)
        
        # Apply the patch
        patchset = fromstring(adjusted_diff.encode('utf-8'))
        success = patchset.apply(root='/', strip=0)
        
        if success:
            # Read the patched content
            with open(temp_path, 'r') as f:
                new_content = f.read()
            return True, new_content, meta
        else:
            # Get any error messages from the log
            error_msg = log_capture.getvalue().strip()
            if error_msg:
                return False, f"Patch failed: {error_msg}", meta
            return False, "Failed to apply patch (no specific error message)", meta
            
    except Exception as e:
        # Get any error messages from the log
        error_msg = log_capture.getvalue().strip()
        if error_msg:
            return False, f"Error applying patch: {error_msg}", meta
        return False, f"Error applying patch: {str(e)}", meta
    finally:
        # Clean up
        patch_logger.removeHandler(log_handler)
        log_handler.close()
        try:
            os.unlink(temp_path)
        except:
            pass

@tool(
    description="""Allows me to modify the content portion of a memory file (excluding frontmatter) by providing a unified diff string. The diff should be created based on the content returned by read_memory, ignoring frontmatter. The diff should show the desired changes in unified diff format (with --- and +++ headers, @@ markers, and +/- line prefixes). This is useful for making precise modifications to specific parts of a file while leaving the rest unchanged.""",
    filepath="The path to the file relative to the memory root (e.g., 'concepts/physics.md')",
    diff_content="A unified diff string showing the desired changes to the content portion only",
    safe=True
)
def patch_memory_content(
    filepath: str,
    diff_content: str
) -> str:
    """Applies a unified diff to modify only the content portion of a memory file"""
    # Validate filepath
    validate_filepath(filepath)
    filepath = ensure_md_extension(filepath)
    
    # Resolve the full path and check it's within allowed directory
    full_path = (PATHS.ai_memory / filepath).resolve()
    try:
        full_path.relative_to(PATHS.ai_memory)
    except ValueError:
        raise ValueError("Invalid filepath: attempted to access outside of allowed directory")
    
    if not full_path.exists():
        return f"Error: File {filepath} does not exist"
    
    # Apply the patch
    success, new_content, meta = apply_content_patch(full_path, diff_content)
    
    if success:
        # Update timestamp
        meta['last_updated'] = datetime.now().isoformat()
        
        # Write back with frontmatter
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter_to_text(meta) + new_content)
        
        return f"Successfully applied patch to content of {filepath}"
    else:
        return f"Failed to apply patch to {filepath}: {new_content}"

# Export the tools
TOOLS = [
    memory_system_introduction,
    create_memory,
    read_memory,
    list_memories,
    append_memory,
    patch_memory_content,
    # search_memories # Deactivated as it's not very useful
]
