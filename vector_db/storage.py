"""
Storage module for vector database using SQLite.

This module provides classes for interacting with the SQLite database
that stores document metadata, chunks, and vector embeddings.
"""

import json
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
import pickle
import os
import numpy as np
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorStorage:
    """
    SQLite-based storage for document metadata, chunks, and vector embeddings.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the SQLite storage.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._initialize_db()
        self._connection = None
    
    def _initialize_db(self) -> None:
        """
        Initialize the database schema if it doesn't exist.
        Creates tables for documents, chunks, and embeddings.
        """
        # Create directory if it doesn't exist
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            start_pos INTEGER NOT NULL,
            end_pos INTEGER NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id INTEGER NOT NULL,
            embedding BLOB NOT NULL,
            model_name TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (chunk_id) REFERENCES chunks (id) ON DELETE CASCADE
        )
        """)
        
        # Create indices for faster querying
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_file_path ON documents (file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks (document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON embeddings (chunk_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_model_name ON embeddings (model_name)")
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        """
        Get a connection to the SQLite database.
        Creates a new connection if one doesn't exist.
        
        Returns:
            SQLite connection object
        """
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
        return self._connection
    
    def close_connection(self):
        """
        Close the SQLite connection if it exists.
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None
    
    def begin_transaction(self):
        """
        Begin a new transaction.
        
        Returns:
            SQLite connection object
        """
        conn = self.get_connection()
        conn.execute("BEGIN TRANSACTION")
        return conn
    
    def commit_transaction(self):
        """
        Commit the current transaction.
        """
        if self._connection is not None:
            self._connection.commit()
    
    def rollback_transaction(self):
        """
        Rollback the current transaction.
        """
        if self._connection is not None:
            self._connection.rollback()
    
    def delete_document(self, file_path: str) -> bool:
        """
        Delete a document and all its associated chunks and embeddings.
        
        Args:
            file_path: Path of the document to delete
            
        Returns:
            True if document was found and deleted, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Find document id
        cursor.execute("SELECT id FROM documents WHERE file_path = ?", (file_path,))
        result = cursor.fetchone()
        
        if result is None:
            return False
        
        document_id = result[0]
        
        # Due to ON DELETE CASCADE, deleting the document will also delete
        # associated chunks and embeddings
        cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        
        deleted = cursor.rowcount > 0
        
        # Don't commit here if we're in a transaction
        # The calling code should handle commits
        
        return deleted
    
    def document_exists(self, file_path: str) -> bool:
        """
        Check if a document exists in the database.
        
        Args:
            file_path: Path of the document to check
            
        Returns:
            True if document exists, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM documents WHERE file_path = ?", (file_path,))
        result = cursor.fetchone()
        
        return result is not None
    
    def get_document_timestamp(self, file_path: str) -> Optional[str]:
        """
        Get the timestamp of a document.
        
        Args:
            file_path: Path of the document
            
        Returns:
            Timestamp string if document exists, None otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT timestamp FROM documents WHERE file_path = ?", (file_path,))
        result = cursor.fetchone()
        
        return result[0] if result else None
    
    def add_document(self, file_path: str, timestamp: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Add a new document to the database.
        
        Args:
            file_path: Path of the document
            timestamp: Timestamp of the document
            metadata: Additional metadata for the document
            
        Returns:
            ID of the newly created document
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Convert metadata to JSON string
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Get current timestamp in ISO format
        created_at = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO documents (file_path, timestamp, metadata, created_at) VALUES (?, ?, ?, ?)",
            (file_path, timestamp, metadata_json, created_at)
        )
        
        document_id = cursor.lastrowid
        
        # Don't commit here if we're in a transaction
        # The calling code should handle commits
        
        return document_id
    
    def add_chunk(self, document_id: int, chunk_index: int, start_pos: int, end_pos: int, 
                  content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Add a new chunk to the database.
        
        Args:
            document_id: ID of the parent document
            chunk_index: Index of this chunk within the document
            start_pos: Start position in the document
            end_pos: End position in the document
            content: Text content of the chunk
            metadata: Additional metadata for the chunk
            
        Returns:
            ID of the newly created chunk
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Convert metadata to JSON string
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Get current timestamp in ISO format
        created_at = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO chunks (document_id, chunk_index, start_pos, end_pos, content, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (document_id, chunk_index, start_pos, end_pos, content, metadata_json, created_at)
        )
        
        chunk_id = cursor.lastrowid
        
        # Don't commit here if we're in a transaction
        # The calling code should handle commits
        
        return chunk_id
    
    def add_embedding(self, chunk_id: int, embedding: List[float], model_name: str) -> int:
        """
        Add a new embedding to the database.
        
        Args:
            chunk_id: ID of the chunk this embedding represents
            embedding: The vector embedding
            model_name: Name of the embedding model used
            
        Returns:
            ID of the newly created embedding
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Convert embedding to binary blob
        embedding_blob = pickle.dumps(embedding)
        
        # Get current timestamp in ISO format
        created_at = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO embeddings (chunk_id, embedding, model_name, dimension, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chunk_id, embedding_blob, model_name, len(embedding), created_at)
        )
        
        embedding_id = cursor.lastrowid
        
        # Don't commit here if we're in a transaction
        # The calling code should handle commits
        
        return embedding_id
    
    def get_embeddings(self, model_name: str) -> List[Tuple[int, List[float]]]:
        """
        Get all embeddings created with a specific model.
        
        Args:
            model_name: Name of the embedding model
            
        Returns:
            List of (chunk_id, embedding) tuples
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT chunk_id, embedding FROM embeddings WHERE model_name = ?",
            (model_name,)
        )
        
        results = cursor.fetchall()
        
        # Deserialize embeddings
        return [(chunk_id, pickle.loads(embedding_blob)) for chunk_id, embedding_blob in results]
    
    def get_chunk_by_id(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a chunk by its ID.
        
        Args:
            chunk_id: ID of the chunk
            
        Returns:
            Chunk information dictionary or None if not found
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT c.*, d.file_path, d.timestamp 
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.id = ?
        """, (chunk_id,))
        
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Convert row to dict
        chunk = dict(row)
        
        # Parse JSON metadata
        if chunk['metadata']:
            chunk['metadata'] = json.loads(chunk['metadata'])
        else:
            chunk['metadata'] = {}
        
        return chunk
    
    def get_document_chunks(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Get all chunks for a document.
        
        Args:
            file_path: Path of the document
            
        Returns:
            List of chunk information dictionaries
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT c.* 
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.file_path = ?
        ORDER BY c.chunk_index
        """, (file_path,))
        
        rows = cursor.fetchall()
        
        # Convert rows to dicts and parse JSON metadata
        chunks = []
        for row in rows:
            chunk = dict(row)
            if chunk['metadata']:
                chunk['metadata'] = json.loads(chunk['metadata'])
            else:
                chunk['metadata'] = {}
            chunks.append(chunk)
        
        return chunks
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the database contents.
        
        Returns:
            Dictionary with statistics
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get document count
        cursor.execute("SELECT COUNT(*) FROM documents")
        document_count = cursor.fetchone()[0]
        
        # Get chunk count
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]
        
        # Get embedding count by model
        cursor.execute("""
        SELECT model_name, COUNT(*) 
        FROM embeddings 
        GROUP BY model_name
        """)
        embedding_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            "document_count": document_count,
            "chunk_count": chunk_count,
            "embedding_counts": embedding_counts,
            "database_path": self.db_path,
            "database_size_bytes": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        } 