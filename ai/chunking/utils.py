"""
Utility functions for the chunking module.
"""

import json
from typing import List, Dict, Any, Optional
from .chunker import Chunk


def chunks_to_dict(chunks: List[Chunk]) -> List[Dict[str, Any]]:
    """
    Convert a list of Chunk objects to a list of dictionaries.
    
    Args:
        chunks: List of Chunk objects
        
    Returns:
        List of dictionaries representing the chunks
    """
    return [
        {
            "id": chunk.id,
            "content": chunk.content,
            "start_pos": chunk.start_pos,
            "end_pos": chunk.end_pos,
            "metadata": chunk.metadata
        }
        for chunk in chunks
    ]


def chunks_to_json(chunks: List[Chunk], indent: Optional[int] = 2) -> str:
    """
    Convert a list of Chunk objects to a JSON string.
    
    Args:
        chunks: List of Chunk objects
        indent: Indentation level for JSON formatting
        
    Returns:
        JSON string representing the chunks
    """
    return json.dumps(chunks_to_dict(chunks), indent=indent)


def display_chunks(chunks: List[Chunk], 
                   content_preview_length: int = 50) -> None:
    """
    Display a summary of chunks for inspection.
    
    Args:
        chunks: List of Chunk objects
        content_preview_length: Number of characters to show in content preview
    """
    for chunk in chunks:
        content_preview = chunk.content[:content_preview_length]
        if len(chunk.content) > content_preview_length:
            content_preview += "..."
            
        print(f"Chunk {chunk.id} ({chunk.start_pos}-{chunk.end_pos}, {len(chunk.content)} chars):")
        print(f"  Content: {content_preview}")
        print(f"  Metadata: {chunk.metadata}")
        print()


def load_text_file(file_path: str) -> str:
    """
    Load text from a file.
    
    Args:
        file_path: Path to the text file
        
    Returns:
        Text content of the file
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    

def save_chunks_to_file(chunks: List[Chunk], 
                         file_path: str, 
                         format: str = "json") -> None:
    """
    Save chunks to a file.
    
    Args:
        chunks: List of Chunk objects
        file_path: Path to save the chunks
        format: Format to save the chunks in ('json' or 'text')
    """
    if format.lower() == "json":
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(chunks_to_json(chunks))
    elif format.lower() == "text":
        with open(file_path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(f"--- Chunk {chunk.id} ---\n")
                f.write(chunk.content)
                f.write("\n\n")
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'json' or 'text'.") 