"""
Similarity search module for vector database.

This module provides various similarity metrics and search functionality
for finding the most similar vectors to a query vector.
"""

from abc import ABC, abstractmethod
import numpy as np
from typing import List, Tuple, Dict, Any, Optional, Union


class SimilarityMetric(ABC):
    """
    Abstract base class for similarity metrics.
    """
    
    @abstractmethod
    def calculate(self, query_vector: List[float], document_vectors: List[List[float]]) -> List[float]:
        """
        Calculate similarity scores between a query vector and a list of document vectors.
        
        Args:
            query_vector: The query vector
            document_vectors: List of document vectors to compare against
            
        Returns:
            List of similarity scores (higher is more similar)
        """
        pass


class CosineSimilarity(SimilarityMetric):
    """
    Cosine similarity metric implementation.
    Measures the cosine of the angle between two vectors.
    """
    
    def calculate(self, query_vector: List[float], document_vectors: List[List[float]]) -> List[float]:
        """
        Calculate cosine similarity scores.
        
        Args:
            query_vector: The query vector
            document_vectors: List of document vectors to compare against
            
        Returns:
            List of similarity scores (higher is more similar)
        """
        # Convert to numpy arrays for efficiency
        query_np = np.array(query_vector)
        docs_np = np.array(document_vectors)
        
        # Normalize query vector
        query_norm = np.linalg.norm(query_np)
        if query_norm > 0:
            query_np = query_np / query_norm
        
        # Normalize document vectors
        norms = np.linalg.norm(docs_np, axis=1, keepdims=True)
        # Avoid division by zero
        norms[norms == 0] = 1
        normalized_docs = docs_np / norms
        
        # Calculate dot products (cosine similarity for normalized vectors)
        similarities = np.dot(normalized_docs, query_np)
        
        return similarities.tolist()


class EuclideanDistance(SimilarityMetric):
    """
    Euclidean distance metric implementation.
    Measures the straight-line distance between two vectors.
    Note: Returns similarity scores (negative distance), so higher is better.
    """
    
    def calculate(self, query_vector: List[float], document_vectors: List[List[float]]) -> List[float]:
        """
        Calculate negative Euclidean distance scores.
        
        Args:
            query_vector: The query vector
            document_vectors: List of document vectors to compare against
            
        Returns:
            List of similarity scores (higher is more similar)
        """
        # Convert to numpy arrays for efficiency
        query_np = np.array(query_vector)
        docs_np = np.array(document_vectors)
        
        # Calculate squared differences
        squared_diff = np.square(docs_np - query_np)
        
        # Sum along rows and take square root
        distances = np.sqrt(np.sum(squared_diff, axis=1))
        
        # Convert to similarity score (negative distance, so higher is better)
        return (-distances).tolist()


class DotProductSimilarity(SimilarityMetric):
    """
    Dot product similarity metric implementation.
    Simple inner product between vectors.
    """
    
    def calculate(self, query_vector: List[float], document_vectors: List[List[float]]) -> List[float]:
        """
        Calculate dot product similarity scores.
        
        Args:
            query_vector: The query vector
            document_vectors: List of document vectors to compare against
            
        Returns:
            List of similarity scores (higher is more similar)
        """
        # Convert to numpy arrays for efficiency
        query_np = np.array(query_vector)
        docs_np = np.array(document_vectors)
        
        # Calculate dot products
        similarities = np.dot(docs_np, query_np)
        
        return similarities.tolist()


class VectorSearcher:
    """
    Search engine for finding similar vectors using configurable similarity metrics.
    """
    
    def __init__(self, similarity_metric: Optional[SimilarityMetric] = None):
        """
        Initialize the vector searcher.
        
        Args:
            similarity_metric: The similarity metric to use (defaults to CosineSimilarity)
        """
        self.similarity_metric = similarity_metric or CosineSimilarity()
    
    def search(self, query_vector: List[float], document_vectors: List[List[float]], 
               top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Search for the most similar vectors to the query vector.
        
        Args:
            query_vector: The query vector
            document_vectors: List of document vectors to search
            top_k: Number of top results to return
            
        Returns:
            List of (index, score) tuples for the top_k most similar vectors
        """
        if not document_vectors:
            return []
        
        # Calculate similarity scores
        scores = self.similarity_metric.calculate(query_vector, document_vectors)
        
        # Create (index, score) pairs
        indexed_scores = [(i, score) for i, score in enumerate(scores)]
        
        # Sort by score in descending order
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k results
        return indexed_scores[:top_k]
    
    def batch_search(self, query_vectors: List[List[float]], document_vectors: List[List[float]],
                    top_k: int = 10) -> List[List[Tuple[int, float]]]:
        """
        Perform batch search for multiple query vectors.
        
        Args:
            query_vectors: List of query vectors
            document_vectors: List of document vectors to search
            top_k: Number of top results to return for each query
            
        Returns:
            List of lists of (index, score) tuples for each query
        """
        return [self.search(query, document_vectors, top_k) for query in query_vectors]
    
    def set_similarity_metric(self, similarity_metric: SimilarityMetric) -> None:
        """
        Change the similarity metric.
        
        Args:
            similarity_metric: The new similarity metric to use
        """
        self.similarity_metric = similarity_metric 