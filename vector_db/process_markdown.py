#!/usr/bin/env python
"""
Script to process all markdown files in a specified folder and add them to the vector database.
"""

import os
import sys
import argparse
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Add the appropriate paths to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Now import modules using relative imports
from .vector_db import VectorDB
from .storage import VectorStorage
from .similarity import CosineSimilarity
from ai.chunking.chunker import Chunker
from ai.chunking.strategies import SimpleChunker, LLMChunker
from ai.embeddings import OpenAIEmbedder

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def find_markdown_files(folder_path: str, recursive: bool = True) -> List[str]:
    """
    Find all markdown files in the specified folder.
    
    Args:
        folder_path: Path to the folder to search in
        recursive: Whether to search recursively in subfolders
        
    Returns:
        List of paths to markdown files
    """
    markdown_files = []
    folder_path = os.path.abspath(folder_path)
    
    if recursive:
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(('.md', '.markdown')):
                    markdown_files.append(os.path.join(root, file))
    else:
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.md', '.markdown')):
                markdown_files.append(os.path.join(folder_path, file))
    
    return markdown_files


def process_markdown_files(
    folder_path: str,
    db_path: str,
    recursive: bool = True,
    max_chunk_size: Optional[int] = 2000,
    overlap: int = 0,
    update_mode: str = "update_if_newer",
    api_key: Optional[str] = None,
    model_name: str = "text-embedding-3-small",
    batch_size: int = 8
) -> int:
    """
    Process all markdown files in the specified folder and add them to the vector database.
    
    Args:
        folder_path: Path to the folder containing markdown files
        db_path: Path to the vector database
        recursive: Whether to search recursively in subfolders
        max_chunk_size: Maximum size of each chunk (for chunker configuration)
        overlap: Overlap between chunks (for chunker configuration)
        update_mode: How to handle existing documents (error, skip, update_if_newer, force)
        api_key: OpenAI API key (if not provided, will use OPENAI_API_KEY environment variable)
        model_name: Embedding model name
        batch_size: Number of embeddings to process in a batch
        
    Returns:
        Number of files processed
    """
    # Initialize components
    chunker = Chunker(LLMChunker(max_direct_tokens=2000, max_chunk_size=max_chunk_size, overlap=overlap))
    embedder = OpenAIEmbedder(model_name=model_name, api_key=api_key, batch_size=batch_size)
    
    # Initialize vector database
    db = VectorDB(db_path, chunker, embedder)
    
    try:
        # Find all markdown files
        markdown_files = find_markdown_files(folder_path, recursive)
        logger.info(f"Found {len(markdown_files)} markdown files")
        
        # Process each file
        processed_count = 0
        skipped_count = 0
        error_count = 0
        total_chunks = 0
        start_time = time.time()
        
        for file_path in markdown_files:
            try:
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
        
        elapsed_time = time.time() - start_time
        logger.info(f"Finished processing {processed_count} files with {total_chunks} total chunks in {elapsed_time:.2f} seconds")
        logger.info(f"Skipped: {skipped_count} files, Errors: {error_count} files")
        
        # Show database statistics
        stats = db.get_statistics()
        logger.info(f"Database statistics: {stats}")
        
        return processed_count
    
    finally:
        # Ensure database connection is properly closed
        if 'db' in locals():
            db.close()
            logger.info("Database connection closed")


def main():
    """Main function for the script."""
    parser = argparse.ArgumentParser(description="Process markdown files and add them to a vector database")
    
    parser.add_argument(
        "folder_path",
        help="Path to the folder containing markdown files"
    )
    parser.add_argument(
        "--db-path", 
        default="data/vector_db.sqlite",
        help="Path to the vector database (default: data/vector_db.sqlite)"
    )
    parser.add_argument(
        "--recursive", 
        action="store_true",
        help="Search recursively in subfolders"
    )
    parser.add_argument(
        "--max-chunk-size", 
        type=int,
        default=2000,
        help="Maximum size of each chunk (default: 2000)"
    )
    parser.add_argument(
        "--overlap", 
        type=int,
        default=50,
        help="Overlap between chunks (default: 50)"
    )
    parser.add_argument(
        "--update-mode",
        choices=["error", "skip", "update_if_newer", "force"],
        default="update_if_newer",
        help="How to handle existing documents (default: update_if_newer)"
    )
    parser.add_argument(
        "--model-name", 
        default="text-embedding-3-small",
        help="Name of the embedding model (default: text-embedding-3-small)"
    )
    parser.add_argument(
        "--batch-size", 
        type=int,
        default=8,
        help="Batch size for embedding API calls (default: 8)"
    )
    
    args = parser.parse_args()
    
    # Check if OPENAI_API_KEY environment variable is set
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment variables")
        print("Please set the OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    # Create database directory if it doesn't exist
    db_dir = os.path.dirname(args.db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    # Process markdown files
    processed_count = process_markdown_files(
        folder_path=args.folder_path,
        db_path=args.db_path,
        recursive=args.recursive,
        max_chunk_size=args.max_chunk_size,
        overlap=args.overlap,
        update_mode=args.update_mode,
        api_key=api_key,
        model_name=args.model_name,
        batch_size=args.batch_size
    )
    
    print(f"Processed {processed_count} markdown files")


if __name__ == "__main__":
    main() 