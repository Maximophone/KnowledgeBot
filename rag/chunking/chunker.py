"""
Core chunking module that provides the base interface and data structures.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Chunk:
    """
    A chunk of text from a document with associated metadata.
    """
    id: int
    content: str
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def size(self) -> int:
        """
        Return the size of the chunk in characters.
        This could be extended to count tokens instead.
        """
        return len(self.content)


class ChunkingStrategy(ABC):
    """
    Abstract base class for chunking strategies.
    """
    
    @abstractmethod
    def chunk(self, text: str, **kwargs) -> List[Chunk]:
        """
        Split text into chunks according to the strategy.
        
        Args:
            text: The text to chunk
            **kwargs: Additional strategy-specific parameters
            
        Returns:
            List of Chunk objects
        """
        pass


class Chunker:
    """
    Main chunking interface that applies a strategy to a document.
    """
    
    def __init__(self, strategy: ChunkingStrategy):
        """
        Initialize the chunker with a specific strategy.
        
        Args:
            strategy: The chunking strategy to use
        """
        self.strategy = strategy
    
    def chunk(self, text: str, **kwargs) -> List[Chunk]:
        """
        Split text into chunks using the current strategy.
        
        Args:
            text: The text to chunk
            **kwargs: Additional strategy-specific parameters
            
        Returns:
            List of Chunk objects
        """
        return self.strategy.chunk(text, **kwargs)
    
    def set_strategy(self, strategy: ChunkingStrategy) -> None:
        """
        Change the chunking strategy.
        
        Args:
            strategy: The new chunking strategy to use
        """
        self.strategy = strategy 