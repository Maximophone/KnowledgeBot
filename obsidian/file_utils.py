"""
File utility functions for Obsidian integration.
"""

import os
import glob
from pathlib import Path
from typing import List, Optional
from obsidian.pdf_utils import extract_text_from_pdf  # for PDF extraction
from config.paths import PATHS

# Use paths from config (cross-platform compatible)
VAULT_PATH = str(PATHS.vault_path)


def get_search_paths() -> List[str]:
    """
    Get the list of search paths based on the current platform.
    Uses the vault path from config and adds platform-appropriate code paths.
    """
    paths = [VAULT_PATH]
    
    # Add user code directory based on platform
    home = Path.home()
    code_path = home / "code"
    if code_path.exists():
        paths.append(str(code_path))
    
    return paths


SEARCH_PATHS = get_search_paths()


def resolve_file_path(fname: str, subfolder: str = "") -> Optional[str]:
    """
    Resolve a file path based on various input formats.
    
    Args:
        fname (str): Filename or path
        subfolder (str): Subfolder to search within each search path
    
    Returns:
        Optional[str]: Resolved file path or None if not found
    """
    if fname.startswith("[[") and fname.endswith("]]"):
        fname = fname[2:-2].split("|")[0]
        return resolve_vault_fname(fname)
    
    potential_names = [fname, f"{fname}.md"]
    
    for base_path in SEARCH_PATHS:
        for name in potential_names:
            full_path = os.path.join(base_path, subfolder, name)
            if os.path.isfile(full_path):
                return full_path
    
    return None

def get_file_contents(fpath: str) -> str:
    """
    Read the contents of a file.
    
    Args:
        fpath (str): Path to the file
    
    Returns:
        str: File contents or error message
    """
    if fpath.endswith(".pdf"):
        return extract_text_from_pdf(fpath)
    
    try:
        with open(fpath, "rb") as f:
            return f.read().decode('utf-8', errors='replace')
    except Exception as e:
        return f"Error reading file {fpath}: {str(e)}"

def get_markdown_files(directory: str, exclude_paths: List[str] = []) -> List[str]:
    """
    Get all markdown files in a directory and its subdirectories, excluding specified paths.

    Args:
        directory (str): Directory to search
        exclude_paths (List[str]): List of paths to exclude

    Returns:
        List[str]: List of markdown file paths
    """
    search_pattern = os.path.join(directory, '**', '*.md')
    all_files = glob.glob(search_pattern, recursive=True)
    
    # Exclude specified paths
    excluded_files = set()
    for exclude_path in exclude_paths:
        exclude_pattern = os.path.join(directory, exclude_path, '**', '*.md')
        excluded_files.update(glob.glob(exclude_pattern, recursive=True))
    
    return [file for file in all_files if file not in excluded_files]

def find_matching_path(file_list: List[str], end_path: str) -> str:
    """
    Find a matching file path from a list of paths. If multiple paths 
    match, the shortest one is returned

    Args:
        file_list (List[str]): List of file paths
        end_path (str): End of the path to match

    Returns:
        str: Matching file path or None
    """
    normalized_end = os.path.normpath(end_path)
    candidates = []
    for full_path in file_list:
        normalized_full = os.path.normpath(full_path)
        if normalized_full.endswith(normalized_end):
            candidates.append(full_path)
    if len(candidates) == 0:
        return None
    # We pick the shortest path out of the candidates
    return min(candidates, key=lambda x: len(x))

def resolve_vault_fname(fname: str, vault_path: str = None) -> str:
    """
    Resolve a vault filename to its full path.

    Args:
        fname (str): Filename to resolve
        vault_path (str): Path to the vault (defaults to VAULT_PATH from config)

    Returns:
        str: Full path to the file or None if not found
    """
    if vault_path is None:
        vault_path = VAULT_PATH
    fpaths_set = get_markdown_files(vault_path)
    fpath = find_matching_path(fpaths_set, fname+".md")
    return fpath

def remove_frontmatter(contents: str) -> str:
    """
    Remove frontmatter from a markdown file's contents.
    
    Args:
        contents (str): File contents
        
    Returns:
        str: Contents without frontmatter
    """
    return contents.split("---")[2] 
