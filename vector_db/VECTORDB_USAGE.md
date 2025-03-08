# Vector Database Usage Guide

This guide explains how to use the vector database tools included in this project.

## Setup

Before using these tools, you need an OpenAI API key. Set it in your environment:

```
set OPENAI_API_KEY=your_api_key_here
```

## Processing Markdown Files

There are two ways to process markdown files into your vector database:

### Option 1: Using the module-based script (recommended)

```
process_markdown.bat [FOLDER_PATH] [OPTIONS]
```

### Option 2: Using the direct script (if option 1 fails)

```
process_markdown_direct.bat [FOLDER_PATH] [OPTIONS]
```

### Arguments:

- `FOLDER_PATH`: Path to the folder containing markdown files (required)

### Options:

- `--db-path PATH`: Path to the vector database (default: data/vector_db.sqlite)
- `--recursive`: Search recursively in subfolders
- `--max-chunk-size SIZE`: Maximum size of each chunk (default: 1000)
- `--overlap SIZE`: Overlap between chunks (default: 50)
- `--model-name NAME`: Name of the embedding model (default: text-embedding-3-small)
- `--batch-size SIZE`: Batch size for embedding API calls (default: 8)

### Example:

```
process_markdown_direct.bat G:\My Drive\Obsidian --recursive --db-path data\my_notes.sqlite
```

## Searching the Vector Database

There are two ways to search your vector database:

### Option 1: Using the module-based script (recommended)

```
search_vectordb.bat "YOUR QUERY" [OPTIONS]
```

### Option 2: Using the direct script (if option 1 fails)

```
search_vectordb_direct.bat "YOUR QUERY" [OPTIONS]
```

### Arguments:

- `"YOUR QUERY"`: The search query (required, use quotes for multi-word queries)

### Options:

- `--db-path PATH`: Path to the vector database (default: data/vector_db.sqlite)
- `--top-k N`: Number of results to return (default: 5)
- `--show-metadata`: Show metadata for each result
- `--max-content-length N`: Maximum length of content to display (default: 200)
- `--similarity TYPE`: Similarity metric to use (choices: cosine, euclidean, dot_product, default: cosine)
- `--no-highlight`: Disable query term highlighting
- `--model-name NAME`: Name of the embedding model (default: text-embedding-3-small)

### Example:

```
search_vectordb_direct.bat "vector similarity search" --top-k 10 --show-metadata
```

## Common Issues

### Import Errors

If you see errors like `ModuleNotFoundError: No module named 'vector_db'`, try:

1. Use the direct script versions (`process_markdown_direct.bat` or `search_vectordb_direct.bat`)
2. Run the commands from the project root directory
3. Make sure you have all the required dependencies installed

### OPENAI_API_KEY not set

If you see an error about the API key not being set, run:

```
set OPENAI_API_KEY=your_api_key_here
```

### Database file not found

Make sure the database file exists at the specified path. If you're using a custom path with `--db-path`, make sure the directory exists.

### UnicodeDecodeError when processing files

The scripts include automatic handling for file encoding issues. If you still encounter problems, you can try manually specifying different encodings in the script.

## Technical Details

The vector database uses:

1. OpenAI's embedding models to create vector representations of text
2. SQLite to store documents, chunks, and embeddings
3. Cosine similarity (by default) for semantic search

When you process markdown files, each file is:
1. Split into chunks using the SimpleChunker strategy
2. Converted to embeddings using the specified OpenAI model
3. Stored in the SQLite database with metadata

When you search, the system:
1. Converts your query to an embedding using the same model
2. Finds the most similar chunks using the specified similarity metric
3. Returns the chunks with the highest similarity scores 