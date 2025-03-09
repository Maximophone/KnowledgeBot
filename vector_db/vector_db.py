"""
Main VectorDB class that integrates storage, chunking, embedding, and similarity search.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
from datetime import datetime
from pathlib import Path

# Use absolute imports instead of relative imports
from storage import VectorStorage
from similarity import VectorSearcher, SimilarityMetric, CosineSimilarity
from ai.chunking.chunker import Chunker
from ai.chunking.strategies import SimpleChunker
from ai.embeddings import BaseEmbedder, OpenAIEmbedder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorDB:
    """
    Vector database for efficient storage and retrieval of embeddings.
    
    Combines document chunking, embedding generation, and similarity search
    with persistent storage and incremental processing capabilities.
    """
    
    def __init__(
        self,
        db_path: str,
        chunker: Optional[Chunker] = None,
        embedder: Optional[BaseEmbedder] = None,
        similarity_metric: Optional[SimilarityMetric] = None
    ):
        """
        Initialize the VectorDB.
        
        Args:
            db_path: Path to the SQLite database file
            chunker: A Chunker instance (optional, defaults to SimpleChunker)
            embedder: A BaseEmbedder instance (optional, defaults to OpenAIEmbedder)
            similarity_metric: A SimilarityMetric instance (optional, defaults to CosineSimilarity)
        """
        self.db_path = db_path
        self.storage = VectorStorage(db_path)
        
        # Initialize chunker, embedder, and searcher with defaults if not provided
        self.chunker = chunker or Chunker(SimpleChunker())
        self.embedder = embedder or OpenAIEmbedder()
        self.searcher = VectorSearcher(similarity_metric or CosineSimilarity())
        
        # Track of loaded embeddings for search efficiency
        self.embeddings_cache = {}  # model_name -> {chunk_id -> embedding}
        self.chunk_id_to_embedding = {}  # model_name -> {embedding_index -> chunk_id}
        
        logger.info(f"VectorDB initialized with database at {db_path}")
    
    def set_chunker(self, chunker: Chunker) -> None:
        """
        Change the chunker used for document processing.
        
        Args:
            chunker: The new Chunker instance to use
        """
        self.chunker = chunker
    
    def set_embedder(self, embedder: BaseEmbedder) -> None:
        """
        Change the embedder used for vector embedding generation.
        
        Args:
            embedder: The new BaseEmbedder instance to use
        """
        self.embedder = embedder
        # Clear embeddings cache since we're using a new model
        self.embeddings_cache = {}
        self.chunk_id_to_embedding = {}
    
    def set_similarity_metric(self, similarity_metric: SimilarityMetric) -> None:
        """
        Change the similarity metric used for vector search.
        
        Args:
            similarity_metric: The new SimilarityMetric instance to use
        """
        self.searcher.set_similarity_metric(similarity_metric)
    
    def add_document(
        self,
        file_path: str,
        content: str,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        update_mode: str = "error",
        max_chunk_size: Optional[int] = None,
        overlap: int = 0,
        **chunking_kwargs
    ) -> int:
        """
        Add a document to the vector database.
        
        This method:
        1. Chunks the document content
        2. Stores the document metadata
        3. Stores the chunks with positions and content
        4. Generates and stores embeddings for each chunk
        
        Args:
            file_path: Path of the document (used as unique identifier)
            content: Text content of the document
            timestamp: Timestamp of the document (defaults to current time)
            metadata: Additional metadata for the document
            update_mode: How to handle existing documents:
                - "error": Raise an error if document exists (default)
                - "skip": Skip if document exists (silent)
                - "update_if_newer": Update only if timestamp is newer
                - "force": Always replace existing document
            max_chunk_size: Maximum size of each chunk (passed to chunker)
            overlap: Overlap between chunks (passed to chunker)
            **chunking_kwargs: Additional parameters for the chunking strategy
            
        Returns:
            Number of chunks processed and stored
            
        Raises:
            ValueError: If document exists and update_mode is "error"
        """
        # Set default timestamp if not provided
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        # Check if document already exists and handle based on update_mode
        if self.storage.document_exists(file_path):
            if update_mode == "error":
                raise ValueError(f"Document {file_path} already exists. Use update_document() to update it or specify a different update_mode.")
            
            elif update_mode == "skip":
                logger.info(f"Document {file_path} already exists, skipping (update_mode=skip)")
                return 0
                
            elif update_mode == "update_if_newer":
                existing_timestamp = self.storage.get_document_timestamp(file_path)
                if existing_timestamp and existing_timestamp >= timestamp:
                    logger.info(f"Document {file_path} already exists with same or newer timestamp, skipping (update_mode=update_if_newer)")
                    return 0
                logger.info(f"Document {file_path} already exists but has older timestamp, updating")
                self.delete_document(file_path)
                
            elif update_mode == "force":
                logger.info(f"Document {file_path} already exists, replacing (update_mode=force)")
                self.delete_document(file_path)
                
            else:
                raise ValueError(f"Invalid update_mode: {update_mode}. Must be one of: error, skip, update_if_newer, force")
        
        # Set default metadata if not provided
        if metadata is None:
            metadata = {}
        
        # Add file path to metadata
        metadata["file_path"] = file_path
        
        # Store document in database
        document_id = self.storage.add_document(file_path, timestamp, metadata)
        logger.info(f"Added document {file_path} with ID {document_id}")
        
        # Chunk the document
        chunks = self.chunker.chunk(content, max_chunk_size, overlap, **chunking_kwargs)
        logger.info(f"Created {len(chunks)} chunks from document {file_path}")
        
        # Process each chunk
        for chunk_index, chunk in enumerate(chunks):
            # Store chunk in database
            chunk_metadata = chunk.metadata.copy()
            chunk_metadata["chunk_index"] = chunk_index
            
            chunk_id = self.storage.add_chunk(
                document_id=document_id,
                chunk_index=chunk_index,
                start_pos=chunk.start_pos,
                end_pos=chunk.end_pos,
                content=chunk.content,
                metadata=chunk_metadata
            )
            
            # Generate and store embedding
            try:
                embedding = self.embedder.embed_text(chunk.content)[0]
                self.storage.add_embedding(
                    chunk_id=chunk_id,
                    embedding=embedding,
                    model_name=getattr(self.embedder, "model_name", "default")
                )
            except Exception as e:
                logger.error(f"Failed to generate embedding for chunk {chunk_id}: {str(e)}")
        
        # Reset embeddings cache
        self._invalidate_cache()
        
        return len(chunks)
    
    def delete_document(self, file_path: str) -> bool:
        """
        Delete a document and all its associated chunks and embeddings.
        
        Args:
            file_path: Path of the document to delete
            
        Returns:
            True if document was found and deleted, False otherwise
        """
        deleted = self.storage.delete_document(file_path)
        if deleted:
            # Reset embeddings cache
            self._invalidate_cache()
            logger.info(f"Deleted document {file_path}")
        else:
            logger.info(f"Document {file_path} not found, nothing to delete")
        
        return deleted
    
    def update_document(
        self,
        file_path: str,
        content: str,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        create_if_missing: bool = True,
        max_chunk_size: Optional[int] = None,
        overlap: int = 0,
        **chunking_kwargs
    ) -> int:
        """
        Update an existing document (delete and re-add).
        
        Args:
            file_path: Path of the document to update
            content: New text content of the document
            timestamp: New timestamp of the document
            metadata: New metadata for the document
            create_if_missing: If True, create document if it doesn't exist
            max_chunk_size: Maximum size of each chunk
            overlap: Overlap between chunks
            **chunking_kwargs: Additional parameters for the chunking strategy
            
        Returns:
            Number of chunks processed and stored
            
        Raises:
            ValueError: If document doesn't exist and create_if_missing is False
        """
        # Check if document exists
        exists = self.storage.document_exists(file_path)
        
        if not exists and not create_if_missing:
            raise ValueError(f"Document {file_path} does not exist and create_if_missing is False")
        
        # Delete the document if it exists
        if exists:
            logger.info(f"Updating existing document {file_path}")
            self.delete_document(file_path)
        else:
            logger.info(f"Document {file_path} does not exist, creating new")
        
        # Add the document with new content
        return self.add_document(
            file_path=file_path,
            content=content,
            timestamp=timestamp,
            metadata=metadata,
            update_mode="force",  # We've already handled the existence check
            max_chunk_size=max_chunk_size,
            overlap=overlap,
            **chunking_kwargs
        )
    
    def _load_embeddings(self, model_name: Optional[str] = None) -> None:
        """
        Load all embeddings for a specific model into memory for efficient search.
        
        Args:
            model_name: Name of the embedding model (defaults to current embedder's model)
        """
        if model_name is None:
            model_name = getattr(self.embedder, "model_name", "default")
        
        if model_name in self.embeddings_cache:
            # Already loaded
            return
        
        # Load all embeddings for this model
        embeddings_list = self.storage.get_embeddings(model_name)
        
        # Create mappings for efficient search
        embeddings_dict = {}
        chunk_id_to_embedding = {}
        
        for chunk_id, embedding in embeddings_list:
            embeddings_dict[chunk_id] = embedding
        
        self.embeddings_cache[model_name] = embeddings_dict
        
        # Create reverse mapping from index to chunk_id
        chunk_ids = list(embeddings_dict.keys())
        chunk_id_to_embedding[model_name] = {i: chunk_id for i, chunk_id in enumerate(chunk_ids)}
        
        self.chunk_id_to_embedding = chunk_id_to_embedding
        
        logger.info(f"Loaded {len(embeddings_dict)} embeddings for model {model_name}")
    
    def _invalidate_cache(self) -> None:
        """Clear the embeddings cache, forcing a reload on next search."""
        self.embeddings_cache = {}
        self.chunk_id_to_embedding = {}
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        model_name: Optional[str] = None,
        filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for chunks similar to the query text.
        
        Args:
            query: Query text to search for
            top_k: Number of top results to return
            model_name: Name of the embedding model to use for search (defaults to current embedder's model)
            filter_func: Optional function to filter chunks (takes chunk info dict, returns boolean)
            
        Returns:
            List of chunk information dictionaries with similarity scores
        """
        # Use current embedder's model if not specified
        if model_name is None:
            model_name = getattr(self.embedder, "model_name", "default")
        
        # Load embeddings if not already loaded
        if model_name not in self.embeddings_cache:
            self._load_embeddings(model_name)
        
        # Check if we have any embeddings to search
        if not self.embeddings_cache.get(model_name, {}):
            logger.warning(f"No embeddings found for model {model_name}")
            return []
        
        # Generate embedding for the query
        query_embedding = self.embedder.embed_text(query)[0]
        
        # Get document vectors and their IDs
        chunk_ids = list(self.embeddings_cache[model_name].keys())
        document_vectors = [self.embeddings_cache[model_name][chunk_id] for chunk_id in chunk_ids]
        
        # Search for similar vectors
        results = self.searcher.search(query_embedding, document_vectors, top_k=top_k)
        
        # Convert results to chunk information
        search_results = []
        for i, (vector_index, score) in enumerate(results):
            chunk_id = chunk_ids[vector_index]
            chunk_info = self.storage.get_chunk_by_id(chunk_id)
            
            if chunk_info:
                # Skip if filter function is provided and returns False
                if filter_func and not filter_func(chunk_info):
                    continue
                
                # Add similarity score to chunk info
                chunk_info["similarity_score"] = score
                chunk_info["search_rank"] = i + 1
                
                search_results.append(chunk_info)
        
        return search_results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the database contents.
        
        Returns:
            Dictionary with statistics
        """
        return self.storage.get_statistics()
    
    def __repr__(self) -> str:
        """Return a string representation of the VectorDB."""
        stats = self.get_statistics()
        return (
            f"VectorDB(path='{self.db_path}', "
            f"documents={stats['document_count']}, "
            f"chunks={stats['chunk_count']}, "
            f"embeddings={sum(stats['embedding_counts'].values()) if 'embedding_counts' in stats else 0})"
        ) 