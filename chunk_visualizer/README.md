# Vector DB Chunk Visualizer

A standalone web application to visualize document chunks stored in a vector database. This tool helps you understand how documents are chunked for embedding in the vector database and allows you to search across all documents using vector similarity.

## Features

- View a list of all documents in the vector database
- Visualize chunks for any document with clear boundaries
- See metadata for each chunk
- Search within document chunks
- Toggle visibility of chunk metadata
- Toggle chunk highlighting
- **Vector Search**: Search across all documents using semantic similarity

## Getting Started

### Prerequisites

- Python 3.6+
- Access to a vector database SQLite file
- OpenAI API key (for vector search functionality)

### Installation

1. Clone the repository or copy the `chunk_visualizer` directory
2. Install dependencies:

```bash
pip install -r requirements.txt
```

### Running the Application

To start the web application:

```bash
python app.py
```

By default, the application will try to connect to a vector database at `../data/vector_db.sqlite`. You can modify the `DEFAULT_DB_PATH` in `app.py` if your database is located elsewhere.

## Usage

1. Open your web browser and navigate to `http://127.0.0.1:5000/`
2. You'll see a list of all documents in the vector database
3. Click "View Chunks" on any document to see its chunks
4. In the document view:
   - Use the search box to find specific content within chunks
   - Toggle "Show Metadata" to show/hide chunk metadata
   - Toggle "Highlight Chunks" to enable/disable visual chunk highlighting

### Vector Search

The application includes a semantic search feature that uses the vector embeddings:

1. Navigate to the Search page
2. Enter your search query
3. (Optional) Adjust advanced options:
   - Number of results to return
   - Similarity metric (Cosine, Euclidean, Dot Product)
   - Embedding model
4. View semantically relevant results from across all documents

## How It Works

The application connects directly to the SQLite database used by the vector database system. It queries:

1. The `documents` table to show all available documents
2. The `chunks` table to retrieve chunks for a selected document
3. The `embeddings` table for vector search functionality
4. Metadata is parsed from JSON stored in the database

## Architecture

- **Flask Backend**: Handles routing and database queries
- **Bootstrap Frontend**: Provides responsive UI components
- **Dynamic Import**: Special handling to properly import the vector_db module
- **Vector Search**: Integrates with the vector_db module for semantic search

## Customization

You can customize the appearance by modifying the CSS styles in `templates/base.html`, `templates/document.html`, and `templates/search.html`.

## License

This project is open source and available under the MIT License. 