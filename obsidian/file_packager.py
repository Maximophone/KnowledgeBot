"""
# Example usage
repo_path = '/path/to/your/repository'
packaged_repo = package_repository(repo_path)
llm_input = format_for_llm(packaged_repo)
"""

import os
import gitignore_parser
import mimetypes
from git import Repo
from git.exc import InvalidGitRepositoryError
from typing import Tuple, List, Dict

def get_committed_files(repo_path):
    """
    Gets all files from the latest commit in a Git repository.
    
    Args:
        repo_path (str): Path to the Git repository
        
    Returns:
        dict: Dictionary mapping file paths to their contents from the latest commit.
              Returns empty dict if not a valid Git repo.
    """
    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError:
        print(f"Error: {repo_path} is not a valid Git repository.")
        return {}

    committed_files = {}
    
    # Get the current branch
    current_branch = repo.active_branch
    
    # Get the latest commit on the current branch
    latest_commit = current_branch.commit

    # Iterate through the tree of the latest commit
    for blob in latest_commit.tree.traverse():
        if blob.type == 'blob':  # It's a file
            file_path = blob.path
            file_content = blob.data_stream.read().decode('utf-8', errors='ignore')
            committed_files[file_path] = file_content

    return committed_files

def format_for_llm(committed_files):
    formatted_content = ""
    for file_path, content in committed_files.items():
        formatted_content += f"### File: {file_path}\n\n{content}\n\n"
    return formatted_content
