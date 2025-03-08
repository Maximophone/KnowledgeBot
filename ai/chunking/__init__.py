"""
Chunking module for document processing.
Provides strategies for splitting documents into semantically coherent chunks.
"""

from .chunker import Chunker, Chunk, ChunkingStrategy
from .strategies import SimpleChunker, LLMChunker
from .utils import (
    chunks_to_dict, 
    chunks_to_json, 
    display_chunks, 
    load_text_file, 
    save_chunks_to_file
)
from .llm_parser import (
    parse_json_response,
    validate_chunk_schema,
    extract_chunks_from_markers,
    format_error_message
)

__all__ = [
    # Core classes
    'Chunker',
    'Chunk',
    'ChunkingStrategy',
    
    # Chunking strategies
    'SimpleChunker',
    'LLMChunker',
    
    # Utility functions
    'chunks_to_dict',
    'chunks_to_json',
    'display_chunks',
    'load_text_file',
    'save_chunks_to_file',
    
    # LLM parser utilities
    'parse_json_response',
    'validate_chunk_schema',
    'extract_chunks_from_markers',
    'format_error_message'
] 