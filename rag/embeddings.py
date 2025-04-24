"""
Embedding model abstraction module for various vector embedding providers.
This module provides a unified interface for different embedding models.
"""

from abc import ABC, abstractmethod
from typing import List, Union, Optional, Dict, Any
import numpy as np


class BaseEmbedder(ABC):
    """
    Abstract base class for embedding models.
    Defines the interface that all embedder implementations must follow.
    """
    
    @abstractmethod
    def embed_text(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Generate embeddings for the given text(s).
        
        Args:
            texts: A single text string or a list of text strings to embed
            
        Returns:
            A list of embedding vectors (each vector is a list of floats)
        """
        pass
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of the embedding vectors produced by this embedder.
        
        Returns:
            The dimension (number of elements) of the embedding vectors
        """
        pass


class OpenAIEmbedder(BaseEmbedder):
    """
    Implementation of the BaseEmbedder using OpenAI's embedding models.
    """
    
    def __init__(self, model_name: str = "text-embedding-3-small", api_key: Optional[str] = None, 
                 batch_size: int = 8):
        """
        Initialize the OpenAI embedder.
        
        Args:
            model_name: The name of the OpenAI embedding model to use
            api_key: OpenAI API key (if None, will use environment variable)
            batch_size: Maximum number of texts to embed in a single API call
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("The 'openai' package is required. Install it with 'pip install openai'.")
        
        self.model_name = model_name
        self.client = OpenAI(api_key=api_key)
        self.batch_size = batch_size
        
        # Mapping of model names to their dimensions
        self.model_dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536
        }
    
    def embed_text(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Generate embeddings for the given text(s) using OpenAI's API.
        
        Args:
            texts: A single text string or a list of text strings to embed
            
        Returns:
            A list of embedding vectors (each vector is a list of floats)
        """
        if isinstance(texts, str):
            texts = [texts]
        
        all_embeddings = []
        
        # Process in batches to respect API limits
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i+self.batch_size]
            
            response = self.client.embeddings.create(
                input=batch,
                model=self.model_name
            )
            
            # Extract embeddings from response
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of the embedding vectors produced by this embedder.
        
        Returns:
            The dimension (number of elements) of the embedding vectors
        """
        if self.model_name in self.model_dimensions:
            return self.model_dimensions[self.model_name]
        
        # If model dimension is unknown, get it by embedding a test string
        test_embedding = self.embed_text("Test string to determine embedding dimension")
        return len(test_embedding[0]) 