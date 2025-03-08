# Vector Database

A lightweight, customizable vector database for storing, managing, and searching document embeddings.

## Features

- **Incremental Processing**: Documents are processed and saved as soon as they're added, allowing for gradual database building and resuming operations.
- **Modular Design**: Swap out components such as chunking strategies, embedding models, and similarity metrics.
- **SQLite Storage**: Efficient, reliable storage of documents, chunks, and vector embeddings.
- **Document Management**: Easy addition, updating, and deletion of documents.
- **Search Capabilities**: Fast vector similarity search with customizable metrics.

## Components

The vector database consists of several modular components:

1. **VectorDB**: Main class that orchestrates the entire system
2. **VectorStorage**: SQLite-based storage for document metadata, chunks, and embeddings
3. **VectorSearcher**: Similarity search engine with configurable metrics
4. **Chunker**: Text chunking strategy (from `ai.chunking` module)
5. **Embedder**: Vector embedding model (from `ai.embeddings` module)

## Command-Line Tools

The package provides two command-line tools for working with the vector database:

### Markdown Processor

Process all markdown files in a folder and add them to the vector database:

```bash
python vector_db/process_markdown.py [FOLDER_PATH] [OPTIONS]
```

Options:
- `--db-path`: Path to the vector database (default: data/vector_db.sqlite)
- `--recursive`: Search recursively in subfolders
- `--max-chunk-size`: Maximum size of each chunk (default: 1000)
- `--overlap`: Overlap between chunks (default: 50)
- `--model-name`: Name of the embedding model (default: text-embedding-3-small)
- `--batch-size`: Batch size for embedding API calls (default: 8)

Example:
```bash
python vector_db/process_markdown.py docs/ --recursive --max-chunk-size 800 --db-path my_vector_db.sqlite
```

### Search Tool

Search the vector database from the command line:

```bash
python vector_db/search_cli.py [QUERY] [OPTIONS]
```

Options:
- `--db-path`: Path to the vector database (default: data/vector_db.sqlite)
- `--top-k`: Number of results to return (default: 5)
- `--show-metadata`: Show metadata for each result
- `--max-content-length`: Maximum length of content to display (default: 200)
- `--similarity`: Similarity metric to use (choices: cosine, euclidean, dot_product, default: cosine)
- `--no-highlight`: Disable query term highlighting
- `--model-name`: Name of the embedding model (default: text-embedding-3-small)

Example:
```bash
python vector_db/search_cli.py "vector similarity search" --top-k 10 --show-metadata --similarity euclidean
```

## Usage

### Basic Usage

```python
from vector_db import VectorDB
from ai.chunking.chunker import Chunker
from ai.chunking.strategies import SimpleChunker
from ai.embeddings import OpenAIEmbedder

# Initialize components
chunker = Chunker(SimpleChunker())
embedder = OpenAIEmbedder(model_name="text-embedding-3-small")

# Create the vector database
db = VectorDB("data/vector_db.sqlite", chunker, embedder)

# Add a document
db.add_document(
    file_path="path/to/document.txt",
    content="Document text content...",
    timestamp="2025-03-08T12:34:56",
    metadata={"author": "John Doe", "tags": ["important", "reference"]}
)

# Search for similar chunks
results = db.search(query="your search query", top_k=5)

# Print results
for result in results:
    print(f"Score: {result['similarity_score']}")
    print(f"Content: {result['content']}")
    print(f"Source: {result['file_path']}")
```

### Swapping Components

```python
from vector_db.similarity import EuclideanDistance
from ai.chunking.strategies import LLMChunker

# Change similarity metric
db.set_similarity_metric(EuclideanDistance())

# Change chunking strategy
llm_chunker = Chunker(LLMChunker())
db.set_chunker(llm_chunker)

# Change embedding model
new_embedder = OpenAIEmbedder(model_name="text-embedding-3-large")
db.set_embedder(new_embedder)
```

### Document Management

```python
# Check if a document exists
exists = db.storage.document_exists("path/to/document.txt")

# Update a document
db.update_document(
    file_path="path/to/document.txt",
    content="Updated document content...",
    timestamp="2025-03-09T15:30:00"
)

# Delete a document
db.delete_document("path/to/document.txt")

# Get database statistics
stats = db.get_statistics()
print(f"Documents: {stats['document_count']}")
print(f"Chunks: {stats['chunk_count']}")
```

## Database Structure

The SQLite database consists of three main tables:

1. **documents**: Stores document metadata
   - id: Primary key
   - file_path: Path to the original document
   - timestamp: Document timestamp
   - metadata: JSON-encoded additional metadata
   - created_at: When the record was created

2. **chunks**: Stores document chunks
   - id: Primary key
   - document_id: Foreign key to documents table
   - chunk_index: Index of the chunk within the document
   - start_pos: Start position in the document
   - end_pos: End position in the document
   - content: Text content of the chunk
   - metadata: JSON-encoded metadata specific to the chunk
   - created_at: When the record was created

3. **embeddings**: Stores vector embeddings for chunks
   - id: Primary key
   - chunk_id: Foreign key to chunks table
   - embedding: Binary blob of the vector embedding
   - model_name: Name of the embedding model used
   - dimension: Dimension of the embedding vector
   - created_at: When the record was created

## Requirements

- Python 3.8+
- SQLite 3
- numpy
- openai (for OpenAIEmbedder)

## Example

See `example.py` for a complete demonstration of the vector database capabilities. 