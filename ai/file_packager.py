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

def get_markdown_files(root_folder: str, exclude_paths: List[str] = [], max_file_length=10000) -> Dict[str, str]:
    markdown_files = {}
    
    # Convert exclude_paths to absolute paths
    exclude_paths = [os.path.abspath(os.path.join(root_folder, path)) for path in exclude_paths]

    for dirpath, dirnames, filenames in os.walk(root_folder):
        # Check if the current directory should be excluded
        if any(dirpath.startswith(exclude) for exclude in exclude_paths):
            continue

        for filename in filenames:
            if filename.endswith('.md'):
                file_path = os.path.join(dirpath, filename)
                
                # Check if the file path should be excluded
                if any(file_path.startswith(exclude) for exclude in exclude_paths):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                    relative_path = os.path.relpath(file_path, root_folder)
                    if len(content) > max_file_length:
                        print(f"Excluding large file: {relative_path}", flush=True)
                        continue
                    markdown_files[relative_path] = content
                except Exception as e:
                    print(f"Error reading file {file_path}: {str(e)}")

    return markdown_files

def format_for_llm(committed_files):
    formatted_content = ""
    for file_path, content in committed_files.items():
        formatted_content += f"### File: {file_path}\n\n{content}\n\n"
    return formatted_content
