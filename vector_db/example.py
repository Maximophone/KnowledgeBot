"""
Example script demonstrating how to use the VectorDB.
"""

import os
import sys
from pathlib import Path
import logging
from datetime import datetime

# Add parent directory to Python path to import from project
sys.path.append(str(Path(__file__).parent.parent))

from vector_db import VectorDB
from vector_db.similarity import CosineSimilarity, EuclideanDistance

from ai.chunking.chunker import Chunker
from ai.chunking.strategies import SimpleChunker
from ai.embeddings import OpenAIEmbedder

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """
    Main function demonstrating VectorDB functionality.
    """
    # Check for OpenAI API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment variables")
        print("Please set the OPENAI_API_KEY environment variable")
        sys.exit(1)

    # Initialize components
    chunker = Chunker(SimpleChunker())
    embedder = OpenAIEmbedder(model_name="text-embedding-3-small", api_key=api_key)
    similarity = CosineSimilarity()
    
    # Initialize VectorDB
    db_path = "data/vector_db.sqlite"
    db = VectorDB(db_path, chunker, embedder, similarity)
    
    # Sample documents
    documents = [
        {
            "file_path": "samples/document1.txt",
            "content": """
            Vector databases are specialized database systems designed to store and query 
            high-dimensional vectors, which are often used to represent embeddings in machine learning.
            These databases are optimized for similarity search operations 
            like finding the nearest neighbors of a query vector.
            """
        },
        {
            "file_path": "samples/document2.txt",
            "content": """
            Python is a high-level, interpreted programming language known for 
            its readability and simplicity. It supports multiple programming paradigms,
            including procedural, object-oriented, and functional programming.
            Python has a large standard library and a vibrant ecosystem of third-party packages.
            """
        },
        {
            "file_path": "samples/document3.txt",
            "content": """
            SQLite is a C-language library that implements a small, fast, self-contained, 
            high-reliability, full-featured, SQL database engine. SQLite is the most used 
            database engine in the world. It is built into all mobile phones and most computers.
            """
        }
    ]
    
    # Add documents to the database
    for doc in documents:
        timestamp = datetime.now().isoformat()
        metadata = {
            "source": "example script",
            "added_at": timestamp
        }
        
        db.add_document(
            file_path=doc["file_path"],
            content=doc["content"],
            timestamp=timestamp,
            metadata=metadata,
            max_chunk_size=500,
            overlap=50
        )
    
    # Show database statistics
    print("\nDatabase Statistics:")
    print("-" * 50)
    stats = db.get_statistics()
    print(f"Documents: {stats['document_count']}")
    print(f"Chunks: {stats['chunk_count']}")
    for model, count in stats.get('embedding_counts', {}).items():
        print(f"Embeddings ({model}): {count}")
    
    # Perform a search
    print("\nSearch Results for 'vector similarity search':")
    print("-" * 50)
    results = db.search(query="vector similarity search", top_k=5)
    for i, result in enumerate(results):
        print(f"Result {i+1} (Score: {result['similarity_score']:.4f}):")
        print(f"  Source: {result['file_path']}")
        print(f"  Content: {result['content'][:150]}...")
        print()
    
    # Change similarity metric and search again
    print("\nChanging similarity metric to Euclidean Distance...")
    db.set_similarity_metric(EuclideanDistance())
    
    print("\nSearch Results with Euclidean Distance for 'database engine':")
    print("-" * 50)
    results = db.search(query="database engine", top_k=5)
    for i, result in enumerate(results):
        print(f"Result {i+1} (Score: {result['similarity_score']:.4f}):")
        print(f"  Source: {result['file_path']}")
        print(f"  Content: {result['content'][:150]}...")
        print()
    
    # Update a document
    print("\nUpdating document...")
    updated_content = """
    SQLite is a C-language library that implements a small, fast, self-contained, 
    high-reliability, full-featured, SQL database engine. SQLite is the most used 
    database engine in the world. It is built into all mobile phones and most computers.
    SQLite offers a serverless architecture and uses a single file for the entire database,
    making it extremely portable and easy to use.
    """
    
    db.update_document(
        file_path="samples/document3.txt",
        content=updated_content,
        timestamp=datetime.now().isoformat(),
        metadata={"source": "example script", "updated": True}
    )
    
    # Search again to see the updated document
    print("\nSearch Results after update for 'portable database':")
    print("-" * 50)
    results = db.search(query="portable database", top_k=5)
    for i, result in enumerate(results):
        print(f"Result {i+1} (Score: {result['similarity_score']:.4f}):")
        print(f"  Source: {result['file_path']}")
        print(f"  Content: {result['content'][:150]}...")
        print()
    
    # Delete a document
    print("\nDeleting document...")
    db.delete_document("samples/document2.txt")
    
    # Show final statistics
    print("\nFinal Database Statistics:")
    print("-" * 50)
    stats = db.get_statistics()
    print(f"Documents: {stats['document_count']}")
    print(f"Chunks: {stats['chunk_count']}")
    for model, count in stats.get('embedding_counts', {}).items():
        print(f"Embeddings ({model}): {count}")


if __name__ == "__main__":
    main() 