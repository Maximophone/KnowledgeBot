#!/usr/bin/env python
"""
Script to vectorize an Obsidian vault and add notes to the vector database.
This tool provides a user-friendly CLI to manage the process with additional
features like directory blacklisting and YAML configuration.
"""

import os
import sys
import yaml
import argparse
import time
import logging
import inquirer
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import colorama
from colorama import Fore, Style
from rich.console import Console
from rich.table import Table

# Add the appropriate paths to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import base script class
from scripts.base_script import BaseScript

# Import vector_db components - use correct import paths
from vector_db import VectorDB
from vector_db.storage import VectorStorage
from vector_db.similarity import CosineSimilarity
from ai.chunking.chunker import Chunker
from ai.chunking.strategies import SimpleChunker, LLMChunker
from ai.embeddings import OpenAIEmbedder
from config.logging_config import setup_logger

# Initialize colorama for colored terminal output
colorama.init()
console = Console()

# Set up logging
logger = setup_logger(__name__)

# Default configuration file path
DEFAULT_CONFIG_PATH = Path(parent_dir) / "config" / "obsidian_vectorizer.yaml"
DEFAULT_CONFIG = {
    "vault_path": "",  # Empty by default, will be set by user
    "db_path": "data/obsidian_vector_db.sqlite",
    "recursive": True,
    "max_chunk_size": 2000,
    "max_direct_tokens": 2000,
    "overlap": 50,
    "update_mode": "update_if_newer",
    "model_name": "text-embedding-3-small",
    "batch_size": 8,
    "blacklist_directories": [
        ".obsidian",
        ".git",
        ".trash",
        "templates",
        ".templates",
        "attachments"
    ]
}


def find_markdown_files(folder_path: str, recursive: bool = True, blacklist_dirs: List[str] = None) -> List[str]:
    """
    Find all markdown files in the specified folder, excluding blacklisted directories.
    
    Args:
        folder_path: Path to the folder to search in
        recursive: Whether to search recursively in subfolders
        blacklist_dirs: List of directory names to exclude
        
    Returns:
        List of paths to markdown files
    """
    markdown_files = []
    folder_path = os.path.abspath(folder_path)
    blacklist_dirs = blacklist_dirs or []
    
    if recursive:
        for root, dirs, files in os.walk(folder_path):
            # Filter out blacklisted directories
            dirs[:] = [d for d in dirs if d not in blacklist_dirs]
            
            for file in files:
                if file.lower().endswith(('.md', '.markdown')):
                    markdown_files.append(os.path.join(root, file))
    else:
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path) and file.lower().endswith(('.md', '.markdown')):
                markdown_files.append(file_path)
    
    return markdown_files


def process_obsidian_vault(
    folder_path: str,
    db_path: str,
    recursive: bool = True,
    max_chunk_size: Optional[int] = 2000,
    max_direct_tokens: Optional[int] = 2000,
    llm_chunker_model_name: Optional[str] = "gemini2.0flash",
    overlap: int = 0,
    update_mode: str = "update_if_newer",
    api_key: Optional[str] = None,
    model_name: str = "text-embedding-3-small",
    batch_size: int = 8,
    blacklist_dirs: List[str] = None
) -> Dict[str, Any]:
    """
    Process all markdown files in the Obsidian vault and add them to the vector database.
    
    Args:
        folder_path: Path to the Obsidian vault
        db_path: Path to the vector database
        recursive: Whether to search recursively in subfolders
        max_chunk_size: Maximum size of each chunk
        overlap: Overlap between chunks
        update_mode: How to handle existing documents
        api_key: OpenAI API key
        model_name: Name of the embedding model
        batch_size: Batch size for embedding API calls
        blacklist_dirs: List of directory names to exclude
        
    Returns:
        Dictionary with statistics about the processing
    """
    # Initialize components
    chunker = Chunker(LLMChunker(model_name=llm_chunker_model_name, max_direct_tokens=max_direct_tokens, max_chunk_size=max_chunk_size, overlap=overlap))
    embedder = OpenAIEmbedder(model_name=model_name, api_key=api_key, batch_size=batch_size)
    
    # Initialize vector database
    db = VectorDB(db_path, chunker, embedder)
    
    try:
        # Find all markdown files, excluding blacklisted directories
        markdown_files = find_markdown_files(folder_path, recursive, blacklist_dirs)
        logger.info(f"Found {len(markdown_files)} markdown files")
        console.print(f"[bold green]Found {len(markdown_files)} markdown files[/bold green]")
        
        # Process each file
        processed_count = 0
        skipped_count = 0
        error_count = 0
        total_chunks = 0
        start_time = time.time()
        
        # Create a progress table
        progress_table = Table(title="Processing Progress")
        progress_table.add_column("Status", style="cyan")
        progress_table.add_column("Count", style="green")
        
        # Display the progress table
        with console.status("[bold green]Processing markdown files...") as status:
            for i, file_path in enumerate(markdown_files, 1):
                try:
                    # Update status message
                    status.update(f"[bold green]Processing file {i}/{len(markdown_files)}: {os.path.basename(file_path)}[/bold green]")
                    
                    # Get file modification time as timestamp
                    mtime = os.path.getmtime(file_path)
                    timestamp = datetime.fromtimestamp(mtime).isoformat()
                    
                    # Read file content with error handling for encoding issues
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        # Try again with error handling
                        logger.warning(f"Encoding issue with {file_path}, trying with errors='replace'")
                        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                    
                    # Skip empty files
                    if not content.strip():
                        logger.warning(f"Skipping empty file: {file_path}")
                        skipped_count += 1
                        continue
                    
                    # Prepare metadata
                    rel_path = os.path.relpath(file_path, os.path.abspath(folder_path))
                    filename = os.path.basename(file_path)
                    metadata = {
                        "filename": filename,
                        "relative_path": rel_path,
                        "file_type": "markdown",
                        "source": "obsidian",
                        "file_size_bytes": os.path.getsize(file_path),
                        "processed_at": datetime.now().isoformat()
                    }
                    
                    # Add document to vector database with the specified update mode
                    try:
                        chunks_added = db.add_document(
                            file_path=file_path,
                            content=content,
                            timestamp=timestamp,
                            metadata=metadata,
                            update_mode=update_mode
                        )
                        
                        if chunks_added > 0:
                            total_chunks += chunks_added
                            processed_count += 1
                            logger.info(f"Processed {file_path} ({chunks_added} chunks)")
                        else:
                            skipped_count += 1
                            logger.info(f"Skipped {file_path} (already processed)")
                    except ValueError as e:
                        if "already exists" in str(e):
                            logger.warning(f"Skipped {file_path}: {str(e)}")
                            skipped_count += 1
                        else:
                            raise
                        
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {str(e)}")
                    error_count += 1
                    console.print(f"[bold red]Error processing file {file_path}: {str(e)}[/bold red]")
        
        elapsed_time = time.time() - start_time
        logger.info(f"Finished processing {processed_count} files with {total_chunks} total chunks in {elapsed_time:.2f} seconds")
        
        # Show database statistics
        stats = db.get_statistics()
        logger.info(f"Database statistics: {stats}")
        
        # Prepare results
        results = {
            "processed_count": processed_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "total_chunks": total_chunks,
            "elapsed_time": elapsed_time,
            "db_stats": stats
        }
        
        return results
    
    finally:
        # Ensure database connection is properly closed
        if 'db' in locals():
            db.close()
            logger.info("Database connection closed")


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file, using defaults if needed.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()
    
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
                if loaded_config:
                    config.update(loaded_config)
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {str(e)}")
            console.print(f"[bold red]Error loading configuration file: {str(e)}[/bold red]")
    else:
        if config_path:
            logger.warning(f"Configuration file {config_path} not found, using defaults")
            console.print(f"[bold yellow]Configuration file not found, using defaults[/bold yellow]")
        else:
            logger.info("No configuration file specified, using defaults")
    
    return config


def save_config(config: Dict[str, Any], config_path: str) -> None:
    """
    Save configuration to a YAML file.
    
    Args:
        config: Configuration dictionary
        config_path: Path to save configuration file
    """
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False)
        logger.info(f"Saved configuration to {config_path}")
        console.print(f"[bold green]Configuration saved to {config_path}[/bold green]")
    except Exception as e:
        logger.error(f"Error saving configuration to {config_path}: {str(e)}")
        console.print(f"[bold red]Error saving configuration: {str(e)}[/bold red]")


class ObsidianVectorizer(BaseScript):
    """Script to vectorize an Obsidian vault and add notes to the vector database."""
    
    @property
    def name(self) -> str:
        return "obsidian_vectorizer"
    
    @property
    def description(self) -> str:
        return "Vectorize an Obsidian vault and add notes to the vector database"
    
    def display_menu(self) -> str:
        """Display the main menu and return the selected action."""
        questions = [
            inquirer.List(
                'action',
                message="Select an action:",
                choices=[
                    ('Vectorize Obsidian Vault', 'vectorize'),
                    ('Edit Configuration', 'edit_config'),
                    ('Display Configuration', 'display_config'),
                    ('Exit', 'exit')
                ]
            )
        ]
        answers = inquirer.prompt(questions)
        return answers['action'] if answers else 'exit'
    
    def edit_config_menu(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Display the configuration editing menu and return the updated configuration."""
        while True:
            # Display current configuration
            self.display_configuration(config)
            
            # Ask which setting to edit
            questions = [
                inquirer.List(
                    'setting',
                    message="Select a setting to edit (or 'Back' to return):",
                    choices=[
                        ('Obsidian Vault Path', 'vault_path'),
                        ('Database Path', 'db_path'),
                        ('Search Recursively', 'recursive'),
                        ('Maximum Chunk Size', 'max_chunk_size'),
                        ("Maximum Direct Tokens", "max_direct_tokens"),
                        ("LLM Chunker Model Name", "llm_chunker_model_name"),
                        ('Chunk Overlap', 'overlap'),
                        ('Update Mode', 'update_mode'),
                        ('Embedding Model', 'model_name'),
                        ('Batch Size', 'batch_size'),
                        ('Blacklisted Directories', 'blacklist_directories'),
                        ('Back to Main Menu', 'back')
                    ]
                )
            ]
            answers = inquirer.prompt(questions)
            
            if not answers or answers['setting'] == 'back':
                break
            
            setting = answers['setting']
            
            # Handle different setting types
            if setting == 'recursive':
                questions = [
                    inquirer.Confirm(
                        'value',
                        message="Enable recursive search?",
                        default=config[setting]
                    )
                ]
                answers = inquirer.prompt(questions)
                if answers:
                    config[setting] = answers['value']
            
            elif setting == 'vault_path':
                # Special handling for vault path to validate it exists
                current_value = config[setting]
                
                questions = [
                    inquirer.Text(
                        'value',
                        message=f"Enter path to your Obsidian vault:",
                        default=current_value,
                        validate=lambda _, x: os.path.isdir(x) or x == "" or "Path must exist or be empty"
                    )
                ]
                answers = inquirer.prompt(questions)
                
                if answers:
                    config[setting] = answers['value']
                    
                    # If path entered, verify it's an Obsidian vault
                    if config[setting] and os.path.isdir(config[setting]):
                        obsidian_dir = os.path.join(config[setting], ".obsidian")
                        if not os.path.isdir(obsidian_dir):
                            console.print(f"[yellow]Warning: The directory at {config[setting]} doesn't appear to be an Obsidian vault (.obsidian folder not found)[/yellow]")
                            
                            confirm = inquirer.prompt([
                                inquirer.Confirm(
                                    'continue',
                                    message="Continue anyway?",
                                    default=True
                                )
                            ])
                            
                            if not confirm or not confirm['continue']:
                                config[setting] = current_value  # Revert to previous value
            
            elif setting == 'update_mode':
                questions = [
                    inquirer.List(
                        'value',
                        message="Select update mode:",
                        choices=[
                            ('Error if document exists', 'error'),
                            ('Skip if document exists', 'skip'),
                            ('Update if document is newer', 'update_if_newer'),
                            ('Force update all documents', 'force')
                        ],
                        default=next((i for i, (_, v) in enumerate(
                            [('Error if document exists', 'error'),
                            ('Skip if document exists', 'skip'),
                            ('Update if document is newer', 'update_if_newer'),
                            ('Force update all documents', 'force')]
                        ) if v == config[setting]), 0)
                    )
                ]
                answers = inquirer.prompt(questions)
                if answers:
                    config[setting] = answers['value']
            
            elif setting == 'blacklist_directories':
                # Display current blacklist
                console.print("\n[bold]Current blacklisted directories:[/bold]")
                for i, directory in enumerate(config[setting], 1):
                    console.print(f"  {i}. {directory}")
                
                # Ask what to do with blacklist
                questions = [
                    inquirer.List(
                        'action',
                        message="Blacklist action:",
                        choices=[
                            ('Add directory', 'add'),
                            ('Remove directory', 'remove'),
                            ('Reset to defaults', 'reset'),
                            ('Cancel', 'cancel')
                        ]
                    )
                ]
                answers = inquirer.prompt(questions)
                
                if answers and answers['action'] == 'add':
                    questions = [
                        inquirer.Text(
                            'directory',
                            message="Enter directory name to blacklist:"
                        )
                    ]
                    dir_answer = inquirer.prompt(questions)
                    if dir_answer and dir_answer['directory']:
                        config[setting].append(dir_answer['directory'])
                
                elif answers and answers['action'] == 'remove':
                    if not config[setting]:
                        console.print("[yellow]No directories to remove[/yellow]")
                        continue
                    
                    questions = [
                        inquirer.List(
                            'directory',
                            message="Select directory to remove:",
                            choices=[(d, d) for d in config[setting]] + [('Cancel', 'cancel')]
                        )
                    ]
                    dir_answer = inquirer.prompt(questions)
                    if dir_answer and dir_answer['directory'] != 'cancel':
                        config[setting].remove(dir_answer['directory'])
                
                elif answers and answers['action'] == 'reset':
                    config[setting] = DEFAULT_CONFIG[setting].copy()
            
            else:
                # Handle text/number settings
                current_value = config[setting]
                value_type = type(current_value)
                
                questions = [
                    inquirer.Text(
                        'value',
                        message=f"Enter new value for {setting}:",
                        default=str(current_value)
                    )
                ]
                answers = inquirer.prompt(questions)
                
                if answers:
                    try:
                        if value_type == int:
                            config[setting] = int(answers['value'])
                        elif value_type == float:
                            config[setting] = float(answers['value'])
                        else:
                            config[setting] = answers['value']
                    except ValueError:
                        console.print("[bold red]Invalid value type. No changes made.[/bold red]")
        
        return config
    
    def display_configuration(self, config: Dict[str, Any]) -> None:
        """Display the current configuration."""
        console.print("\n[bold]Current Configuration:[/bold]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Setting")
        table.add_column("Value")
        
        for key, value in config.items():
            if key == 'blacklist_directories':
                table.add_row(key, ", ".join(value))
            else:
                table.add_row(key, str(value))
        
        console.print(table)
        console.print()
    
    def display_results(self, results: Dict[str, Any]) -> None:
        """Display the processing results."""
        console.print("\n[bold]Processing Results:[/bold]")
        
        table = Table(show_header=True, header_style="bold green")
        table.add_column("Metric")
        table.add_column("Value")
        
        table.add_row("Files Processed", str(results['processed_count']))
        table.add_row("Files Skipped", str(results['skipped_count']))
        table.add_row("Errors", str(results['error_count']))
        table.add_row("Total Chunks", str(results['total_chunks']))
        table.add_row("Processing Time", f"{results['elapsed_time']:.2f} seconds")
        
        console.print(table)
        
        console.print("\n[bold]Database Statistics:[/bold]")
        stats_table = Table(show_header=True, header_style="bold blue")
        stats_table.add_column("Metric")
        stats_table.add_column("Value")
        
        for key, value in results['db_stats'].items():
            stats_table.add_row(key, str(value))
        
        console.print(stats_table)
        console.print()
    
    def run_vectorization(self, folder_path: str, config: Dict[str, Any]) -> None:
        """Run the vectorization process."""
        # Check for OPENAI_API_KEY
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            console.print("[bold red]OPENAI_API_KEY not found in environment variables[/bold red]")
            logger.error("OPENAI_API_KEY not found in environment variables")
            return
        
        # Check that folder path exists
        if not os.path.isdir(folder_path):
            console.print(f"[bold red]Error: The directory '{folder_path}' does not exist[/bold red]")
            logger.error(f"Directory does not exist: {folder_path}")
            return
            
        console.print(f"[bold green]Starting vectorization of {folder_path}[/bold green]")
        
        try:
            # Create database directory if it doesn't exist
            db_dir = os.path.dirname(config['db_path'])
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
            
            # Process markdown files
            results = process_obsidian_vault(
                folder_path=folder_path,
                db_path=config['db_path'],
                recursive=config['recursive'],
                max_chunk_size=config['max_chunk_size'],
                max_direct_tokens=config['max_direct_tokens'],
                llm_chunker_model_name=config['llm_chunker_model_name'],
                overlap=config['overlap'],
                update_mode=config['update_mode'],
                api_key=api_key,
                model_name=config['model_name'],
                batch_size=config['batch_size'],
                blacklist_dirs=config['blacklist_directories']
            )
            
            # Display results
            self.display_results(results)
            
        except Exception as e:
            logger.error(f"Error during vectorization: {str(e)}")
            console.print(f"[bold red]Error during vectorization: {str(e)}[/bold red]")
    
    def run(self, config_path: str = None, vault_path: str = None, run_headless: bool = False, **kwargs):
        """
        Main execution method.
        
        Args:
            config_path: Path to the configuration file
            vault_path: Path to the Obsidian vault (overrides the one in config)
            run_headless: Whether to run without the interactive menu
        """
        # Load configuration
        config_path = config_path or str(DEFAULT_CONFIG_PATH)
        config = load_config(config_path)
        
        # Command-line vault path overrides the one in config
        if vault_path:
            config['vault_path'] = vault_path
        
        # Handle headless mode
        if run_headless:
            # Check if we have a vault path
            if not config['vault_path']:
                console.print("[bold red]Error: No vault path specified in headless mode[/bold red]")
                logger.error("No vault path specified in headless mode")
                return
                
            # Run vectorization directly
            self.run_vectorization(config['vault_path'], config)
            return
        
        # Display welcome banner
        console.print("\n[bold blue]=======================================")
        console.print("[bold blue]      Obsidian Vault Vectorizer      ")
        console.print("[bold blue]=======================================\n")
        
        # Interactive menu loop
        while True:
            action = self.display_menu()
            
            if action == 'exit':
                console.print("[bold green]Goodbye![/bold green]")
                break
            
            elif action == 'vectorize':
                # Check if vault path is in config
                current_vault_path = config['vault_path']
                
                if not current_vault_path or not os.path.isdir(current_vault_path):
                    # If no valid vault path in config, ask for it
                    questions = [
                        inquirer.Text(
                            'vault_path',
                            message="Enter path to your Obsidian vault:",
                            default=current_vault_path if current_vault_path else "",
                            validate=lambda _, x: os.path.isdir(x)
                        )
                    ]
                    answers = inquirer.prompt(questions)
                    if answers:
                        vault_path = answers['vault_path']
                        
                        # Update config with the new path
                        config['vault_path'] = vault_path
                        
                        # Ask to save the path in config
                        save_confirm = inquirer.prompt([
                            inquirer.Confirm(
                                'save_path',
                                message="Save this vault path in your configuration?",
                                default=True
                            )
                        ])
                        
                        if save_confirm and save_confirm['save_path']:
                            save_config(config, config_path)
                    else:
                        continue
                else:
                    vault_path = current_vault_path
                
                self.run_vectorization(vault_path, config)
                
                # Ask if user wants to vectorize another vault
                questions = [
                    inquirer.Confirm(
                        'another_vault',
                        message="Do you want to vectorize another vault?",
                        default=False
                    )
                ]
                answers = inquirer.prompt(questions)
                if answers and answers['another_vault']:
                    # Ask for the new vault path
                    questions = [
                        inquirer.Text(
                            'vault_path',
                            message="Enter path to the new Obsidian vault:",
                            validate=lambda _, x: os.path.isdir(x)
                        )
                    ]
                    answers = inquirer.prompt(questions)
                    if answers:
                        vault_path = answers['vault_path']
                        
                        # Ask to update config with the new path
                        save_confirm = inquirer.prompt([
                            inquirer.Confirm(
                                'save_path',
                                message="Save this vault path in your configuration?",
                                default=True
                            )
                        ])
                        
                        if save_confirm and save_confirm['save_path']:
                            config['vault_path'] = vault_path
                            save_config(config, config_path)
                        
                        # Process the new vault
                        self.run_vectorization(vault_path, config)
            
            elif action == 'edit_config':
                # Edit configuration
                config = self.edit_config_menu(config)
                
                # Ask if user wants to save configuration
                questions = [
                    inquirer.Confirm(
                        'save_config',
                        message="Do you want to save this configuration?",
                        default=True
                    )
                ]
                answers = inquirer.prompt(questions)
                if answers and answers['save_config']:
                    save_config(config, config_path)
            
            elif action == 'display_config':
                # Display configuration
                self.display_configuration(config)
                input("\nPress Enter to continue...")


def main():
    """Command line entry point."""
    parser = argparse.ArgumentParser(
        description="Vectorize an Obsidian vault and add notes to the vector database"
    )
    
    parser.add_argument(
        "--vault-path",
        help="Path to the Obsidian vault (overrides the one in config)"
    )
    parser.add_argument(
        "--config-path",
        default=str(DEFAULT_CONFIG_PATH),
        help=f"Path to the configuration file (default: {DEFAULT_CONFIG_PATH})"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (without interactive menu)"
    )
    
    args = parser.parse_args()
    
    # Run the script
    vectorizer = ObsidianVectorizer()
    vectorizer.run(
        config_path=args.config_path,
        vault_path=args.vault_path,
        run_headless=args.headless
    )


if __name__ == "__main__":
    main() 