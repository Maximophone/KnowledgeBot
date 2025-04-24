from ai.tools import tool
from rag.vector_db import VectorDB
from pathlib import Path
import json
import os

# Default database path
DEFAULT_DB_PATH = "data/obsidian_vector_db.sqlite"

# Initialize the default database if it exists
default_db = None
if os.path.exists(DEFAULT_DB_PATH):
    default_db = VectorDB(DEFAULT_DB_PATH)

@tool(
    description="Search the vectorized Obsidian vault using semantic similarity. Returns relevant chunks of content based on your query.",
    query="The search query to find semantically similar content",
    db_path="Optional custom path to the vector database (defaults to data/obsidian_vault_db.sqlite)",
    top_k="Number of results to return (default: 10)",
    include_metadata="Whether to include full metadata in the results (default: True)",
    safe=True
)
def search_vector_db(
    query: str,
    db_path: str = None,
    top_k: int = 10,
    include_metadata: bool = True
) -> str:
    """Searches the vector database for content similar to the query"""
    
    # Determine which database to use
    db = default_db
    custom_db = None
    
    if db_path and db_path != DEFAULT_DB_PATH:
        # Use a custom database path
        if not os.path.exists(db_path):
            return f"Error: Database file not found at {db_path}"
        try:
            custom_db = VectorDB(db_path)
            db = custom_db
        except Exception as e:
            return f"Error connecting to database at {db_path}: {str(e)}"
    elif not db:
        return f"Error: Default database not found at {DEFAULT_DB_PATH}"
    
    try:
        # Perform the search
        results = db.search(query, top_k=top_k)
        
        # Format the results as markdown
        if not results:
            return "No results found matching your query."
        
        # Build markdown output
        markdown_output = f"# Search Results for: '{query}'\n\n"
        
        for i, result in enumerate(results):
            # Get basic result information
            doc_path = result.get("document_path", "Unknown document")
            content = result.get("content", "No content available")
            score = result.get("similarity_score", 0)
            
            markdown_output += f"## Result {i+1} - {doc_path}\n"
            markdown_output += f"**Similarity Score:** {score:.4f}\n\n"
            
            # Add content
            markdown_output += "```markdown\n"
            markdown_output += content + "\n"
            markdown_output += "```\n\n"
            
            # Add metadata if requested
            if include_metadata:
                metadata = {k: v for k, v in result.items() 
                           if k not in ["content", "document_path", "similarity_score"]}
                if metadata:
                    markdown_output += "**Metadata:**\n"
                    markdown_output += "```json\n"
                    markdown_output += json.dumps(metadata, indent=2) + "\n"
                    markdown_output += "```\n\n"
            
            markdown_output += "---\n\n"
        
        return markdown_output
        
    except Exception as e:
        return f"Error performing search: {str(e)}"
    finally:
        # Clean up any custom database connection
        if custom_db:
            custom_db.close()

# Export the tools
TOOLS = [search_vector_db] 