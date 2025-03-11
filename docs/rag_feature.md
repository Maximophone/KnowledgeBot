# RAG (Retrieval-Augmented Generation) Feature

The RAG feature allows you to query your vector database directly from your Obsidian notes using a simple tag syntax.

## How it Works

The RAG feature uses a vector database that indexes and stores embeddings of your documents, allowing for semantic searching based on the meaning of your query rather than just keyword matching.

When you run a RAG query, the system:
1. Converts your query to an embedding vector
2. Searches the vector database for semantically similar chunks
3. Returns the most relevant chunks with their source information

## Using the RAG Feature

To use the RAG feature, simply create a block with the `<rag!>` tag, add your query, and include a `<reply!>` tag where the results should appear:

```markdown
<rag!>
What are the main components of a vector database?
<reply!/>
</rag!>
```

After saving the file, the system will process the query and insert the search results by replacing the `<reply!>` tag. The output will be formatted in XML:

```markdown
<rag!>
What are the main components of a vector database?
<rag_results>
  <chunk similarity="0.9245">
    <file_path>/path/to/document.md</file_path>
    <position start="1024" end="1536" />
    <content>A vector database consists of several key components: an embedding generation system, a vector storage mechanism, similarity search algorithms, and metadata indexing...</content>
  </chunk>
  <!-- Additional chunks... -->
</rag_results>
</rag!>
```

## Understanding the Results

The results are returned in an XML structure:

- `<rag_results>`: Contains all the search results
- `<chunk>`: An individual result with a similarity score
  - `<file_path>`: Path to the source document
  - `<position>`: Starting and ending character positions in the source document
  - `<content>`: The actual content of the matching chunk

## Options and Configuration

You can adjust the RAG search behavior by adding options to the tag:

```markdown
<rag!top_k=10>
Your query here
<reply!/>
</rag!>
```

Available options:
- `top_k`: Number of results to return (default: 5)
- More options coming soon...

## Troubleshooting

If you encounter any issues with the RAG feature:

1. Ensure your vector database is properly initialized and contains indexed documents
2. Check your query for clarity - more specific queries often yield better results 
3. If you see an error message, try simplifying your query or check the error logs for details

## Related Features

- **Vector Database Management**: See the `vector_db` module documentation for database management tools
- **Document Chunking**: Information on how documents are processed for the vector database 