"""
Implementation of various chunking strategies.
"""

from typing import List, Optional, Dict, Any
from .chunker import ChunkingStrategy, Chunk
import sys
import os

# Add parent directory to path to allow importing from ai module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai.tokens import n_tokens


class SimpleChunker(ChunkingStrategy):
    """
    A simple chunking strategy that divides text into equal-sized chunks.
    This strategy doesn't consider semantic boundaries and simply splits
    by character count.
    """
    
    def chunk(self, text: str, max_chunk_size: Optional[int] = 1000,
              overlap: int = 0, **kwargs) -> List[Chunk]:
        """
        Split text into chunks of equal size.
        
        Args:
            text: The text to chunk
            max_chunk_size: Maximum size of each chunk in characters
            overlap: Number of characters to overlap between chunks
            **kwargs: Additional parameters (ignored in this implementation)
            
        Returns:
            List of Chunk objects
        """
        if max_chunk_size is None:
            max_chunk_size = 1000  # Default chunk size
            
        chunks = []
        text_length = len(text)
        
        if text_length == 0:
            return chunks
            
        # Calculate effective chunk size (accounting for overlap)
        effective_size = max_chunk_size - overlap
        if effective_size <= 0:
            raise ValueError("Overlap must be less than max_chunk_size")
        
        # Create chunks
        position = 0
        chunk_id = 1
        
        while position < text_length:
            # Calculate end position for this chunk
            end_pos = min(position + max_chunk_size, text_length)
            
            # Extract chunk content
            chunk_content = text[position:end_pos]
            
            # Create chunk with metadata
            metadata = {
                "type": "fixed-size",
                "strategy": "simple",
                "char_count": len(chunk_content),
                "token_estimate": n_tokens(chunk_content)
            }
            
            chunk = Chunk(
                id=chunk_id,
                content=chunk_content,
                start_pos=position,
                end_pos=end_pos - 1,  # End position is inclusive
                metadata=metadata
            )
            
            chunks.append(chunk)
            
            # Move position for next chunk, accounting for overlap
            position += effective_size
            chunk_id += 1
            
        return chunks


class LLMChunker(ChunkingStrategy):
    """
    A chunking strategy that uses an LLM to create semantically coherent chunks.
    This is a placeholder for the future implementation.
    """
    
    def __init__(self, ai_client=None, prompt_template=None):
        """
        Initialize the LLM chunker.
        
        Args:
            ai_client: The AI client to use for chunking
            prompt_template: The prompt template to use for the LLM
        """
        self.ai_client = ai_client
        self.prompt_path = "ai/chunking/chunking_prompt.md"
        
        # Load default prompt if none provided
        if prompt_template is None and self.prompt_path:
            try:
                with open(self.prompt_path, "r") as f:
                    self.prompt_template = f.read()
            except:
                self.prompt_template = "Please chunk this document into semantically coherent parts."
        else:
            self.prompt_template = prompt_template
    
    def chunk(self, text: str, max_chunk_size: Optional[int] = None,
              overlap: int = 0, **kwargs) -> List[Chunk]:
        """
        Split text into semantically coherent chunks using an LLM.
        
        Note: This is a placeholder. The actual implementation will be added later.
        
        Args:
            text: The text to chunk
            max_chunk_size: Maximum size of each chunk in tokens
            overlap: Number of tokens to overlap between chunks
            **kwargs: Additional parameters passed to the LLM
            
        Returns:
            List of Chunk objects
        """
        # This is a placeholder that returns a simple fixed-size chunking
        # The actual LLM-based implementation will be added later
        simple_chunker = SimpleChunker()
        return simple_chunker.chunk(text, max_chunk_size, overlap, **kwargs) 