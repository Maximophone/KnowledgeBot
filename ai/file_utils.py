import os
from pathlib import Path
from typing import List, Union

def should_exclude(path: Union[str, Path], exclude_patterns: List[str]) -> bool:
    """
    Checks if a path matches any of the exclusion patterns.
    Patterns can be directory names or paths relative to the root.
    """
    if isinstance(path, str):
        path = Path(path)
    
    # Convert path to string parts for matching
    path_parts = path.parts
    
    for pattern in exclude_patterns:
        pattern_parts = Path(pattern).parts
        
        # Check if pattern matches any part of the path
        for i in range(len(path_parts) - len(pattern_parts) + 1):
            if path_parts[i:i+len(pattern_parts)] == pattern_parts:
                return True
    
    return False

def validate_filepath(filepath: str) -> None:
    """Validates that a filepath is safe to use"""
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
    safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./\'() ')
    invalid_chars = [c for c in filepath if c not in safe_chars]
    if invalid_chars:
        raise ValueError(f"Filepath contains invalid characters: {', '.join(repr(c) for c in invalid_chars)}")

def ensure_md_extension(filename: str) -> str:
    """Ensures the filename has a .md extension"""
    if not filename.endswith('.md'):
        filename += '.md'
    return filename 