#!/usr/bin/env python
"""
CLI tool for searching the vector database.
"""

import os
import sys
import argparse
import logging
import textwrap
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add the appropriate paths to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Now import modules using their file paths directly
sys.path.insert(0, current_dir)
from vector_db import VectorDB  # This will now import from vector_db/__init__.py
from similarity import CosineSimilarity, EuclideanDistance, DotProductSimilarity
from ai.embeddings import OpenAIEmbedder

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def format_result(result: Dict[str, Any], show_metadata: bool = False, 
                 max_content_length: int = 200, highlight_query: Optional[str] = None) -> str:
    """
    Format a search result for display.
    
    Args:
        result: Search result dictionary
        show_metadata: Whether to show metadata
        max_content_length: Maximum length of content to display
        highlight_query: Query terms to highlight in content
        
    Returns:
        Formatted result string
    """
    # Extract fields
    score = result.get('similarity_score', 0)
    rank = result.get('search_rank', 0)
    content = result.get('content', '')
    file_path = result.get('file_path', 'Unknown')
    
    # Truncate content if needed
    if len(content) > max_content_length:
        content = content[:max_content_length] + "..."
    
    # Highlight query terms if specified
    if highlight_query and highlight_query.strip():
        terms = highlight_query.lower().split()
        for term in terms:
            if len(term) > 2:  # Only highlight terms with more than 2 characters
                content = content.replace(term, f"\033[1;33m{term}\033[0m")  # Yellow highlighting
                content = content.replace(term.capitalize(), f"\033[1;33m{term.capitalize()}\033[0m")
    
    # Wrap text for better display
    wrapped_content = textwrap.fill(content, width=80, initial_indent='  ', subsequent_indent='  ')
    
    # Format output
    result_str = [
        f"\033[1;36m[{rank}] Score: {score:.4f}\033[0m",
        f"\033[1;32mSource: {file_path}\033[0m",
        f"{wrapped_content}"
    ]
    
    # Add metadata if requested
    if show_metadata and 'metadata' in result:
        metadata_str = "\n  ".join([f"{k}: {v}" for k, v in result['metadata'].items()])
        result_str.append(f"\033[1;35mMetadata:\033[0m\n  {metadata_str}")
    
    return "\n".join(result_str)


def search_vector_db(
    query: str,
    db_path: str,
    top_k: int = 5,
    show_metadata: bool = False,
    max_content_length: int = 1000,
    similarity_metric: str = "cosine",
    highlight_query: bool = True,
    model_name: str = "text-embedding-3-small",
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search the vector database.
    
    Args:
        query: Search query
        db_path: Path to the vector database
        top_k: Number of results to return
        show_metadata: Whether to show metadata
        max_content_length: Maximum length of content to display
        similarity_metric: Similarity metric to use (cosine, euclidean, dot_product)
        highlight_query: Whether to highlight query terms in results
        model_name: Name of the embedding model
        api_key: OpenAI API key
        
    Returns:
        List of search results
    """
    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)
    
    # Initialize embedder
    embedder = OpenAIEmbedder(model_name=model_name, api_key=api_key)
    
    # Select similarity metric
    if similarity_metric.lower() == "euclidean":
        similarity = EuclideanDistance()
    elif similarity_metric.lower() == "dot_product":
        similarity = DotProductSimilarity()
    else:
        similarity = CosineSimilarity()
    
    # Initialize vector database
    db = VectorDB(db_path, embedder=embedder, similarity_metric=similarity)
    
    # Perform search
    results = db.search(query=query, top_k=top_k)
    
    # Display results
    if not results:
        print("No results found.")
        return []
    
    print(f"\nFound {len(results)} results for query: \"{query}\"")
    print("=" * 80)
    
    for i, result in enumerate(results):
        highlight = query if highlight_query else None
        formatted_result = format_result(
            result, 
            show_metadata=show_metadata, 
            max_content_length=max_content_length,
            highlight_query=highlight
        )
        print(formatted_result)
        
        # Add separator between results
        if i < len(results) - 1:
            print("-" * 80)
    
    return results


def main():
    """Main function for the CLI tool."""
    parser = argparse.ArgumentParser(description="Search the vector database")
    
    parser.add_argument(
        "query",
        help="Search query"
    )
    parser.add_argument(
        "--db-path", 
        default="data/vector_db.sqlite",
        help="Path to the vector database (default: data/vector_db.sqlite)"
    )
    parser.add_argument(
        "--top-k", 
        type=int,
        default=5,
        help="Number of results to return (default: 5)"
    )
    parser.add_argument(
        "--show-metadata", 
        action="store_true",
        help="Show metadata for each result"
    )
    parser.add_argument(
        "--max-content-length", 
        type=int,
        default=10000,
        help="Maximum length of content to display (default: 200)"
    )
    parser.add_argument(
        "--similarity", 
        choices=["cosine", "euclidean", "dot_product"],
        default="cosine",
        help="Similarity metric to use (default: cosine)"
    )
    parser.add_argument(
        "--no-highlight", 
        action="store_true",
        help="Disable query term highlighting"
    )
    parser.add_argument(
        "--model-name", 
        default="text-embedding-3-small",
        help="Name of the embedding model (default: text-embedding-3-small)"
    )
    
    args = parser.parse_args()
    
    # Check if OPENAI_API_KEY environment variable is set
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment variables")
        print("Please set the OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    # Perform search
    search_vector_db(
        query=args.query,
        db_path=args.db_path,
        top_k=args.top_k,
        show_metadata=args.show_metadata,
        max_content_length=args.max_content_length,
        similarity_metric=args.similarity,
        highlight_query=not args.no_highlight,
        model_name=args.model_name,
        api_key=api_key
    )


if __name__ == "__main__":
    main() 