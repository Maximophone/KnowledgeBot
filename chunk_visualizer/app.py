import os
import json
import sqlite3
import base64
import sys
from flask import Flask, render_template, request, jsonify, redirect, url_for
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import directly from vector_db now that the circular import is fixed
from vector_db import VectorDB
from vector_db.similarity import CosineSimilarity, EuclideanDistance, DotProductSimilarity
from ai.embeddings import OpenAIEmbedder

app = Flask(__name__)

# Default path to vector database
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                              'data', 'obsidian_vector_db.sqlite')

def get_db_connection(db_path=None):
    """Connect to the vector database"""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_documents(db_path=None):
    """Get all documents from the vector database"""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Query all documents
    cursor.execute("""
    SELECT id, file_path, timestamp, metadata
    FROM documents
    ORDER BY file_path
    """)
    
    documents = []
    for row in cursor.fetchall():
        doc = dict(row)
        # Parse JSON metadata if it exists
        if doc['metadata']:
            doc['metadata'] = json.loads(doc['metadata'])
            # Base64 encode the metadata to avoid JSON escaping issues
            doc['metadata_b64'] = base64.b64encode(json.dumps(doc['metadata']).encode('utf-8')).decode('utf-8')
        else:
            doc['metadata'] = {}
            doc['metadata_b64'] = ''
        documents.append(doc)
    
    conn.close()
    return documents

def get_document_chunks(file_path, db_path=None):
    """Get all chunks for a document"""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Query all chunks for the document
    cursor.execute("""
    SELECT c.* 
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE d.file_path = ?
    ORDER BY c.chunk_index
    """, (file_path,))
    
    chunks = []
    for row in cursor.fetchall():
        chunk = dict(row)
        # Parse JSON metadata if it exists
        if chunk['metadata']:
            chunk['metadata'] = json.loads(chunk['metadata'])
        else:
            chunk['metadata'] = {}
        chunks.append(chunk)
    
    conn.close()
    return chunks

def vector_search(query, top_k=5, similarity_metric="cosine", model_name="text-embedding-3-small", db_path=None):
    """Search the vector database"""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    # Select similarity metric
    if similarity_metric.lower() == "euclidean":
        similarity = EuclideanDistance()
    elif similarity_metric.lower() == "dot_product":
        similarity = DotProductSimilarity()
    else:
        similarity = CosineSimilarity()
    
    # Initialize embedder
    embedder = OpenAIEmbedder(model_name=model_name)
    
    try:
        # Initialize the actual VectorDB class
        db = VectorDB(db_path, embedder=embedder, similarity_metric=similarity)
        
        # Use the proper search method
        results = db.search(query=query, top_k=top_k)
        
        # Close database connection
        db.close()
        
        return results
    except Exception as e:
        print(f"Error during vector search: {str(e)}")
        raise

@app.route('/')
def index():
    """Home page showing document selection"""
    documents = get_all_documents()
    return render_template('index.html', documents=documents)

@app.route('/document/<path:file_path>')
def document_view(file_path):
    """View a document's chunks"""
    chunks = get_document_chunks(file_path)
    return render_template('document.html', file_path=file_path, chunks=chunks)

@app.route('/search', methods=['GET', 'POST'])
def search():
    """Search page"""
    if request.method == 'POST':
        query = request.form.get('query', '')
        top_k = int(request.form.get('top_k', 5))
        similarity = request.form.get('similarity', 'cosine')
        model = request.form.get('model', 'text-embedding-3-small')
        
        if query:
            try:
                results = vector_search(
                    query=query,
                    top_k=top_k,
                    similarity_metric=similarity,
                    model_name=model
                )
                return render_template('search.html', 
                                   query=query, 
                                   results=results, 
                                   top_k=top_k, 
                                   similarity=similarity,
                                   model=model)
            except Exception as e:
                error_message = str(e)
                return render_template('search.html',
                                   query=query,
                                   error=error_message,
                                   top_k=top_k,
                                   similarity=similarity,
                                   model=model)
        else:
            return redirect(url_for('search'))
    
    return render_template('search.html', 
                       query='', 
                       results=None,
                       error=None,
                       top_k=5, 
                       similarity='cosine',
                       model='text-embedding-3-small')

@app.route('/api/documents')
def api_documents():
    """API endpoint to get all documents"""
    documents = get_all_documents()
    return jsonify(documents)

@app.route('/api/document/<path:file_path>/chunks')
def api_document_chunks(file_path):
    """API endpoint to get chunks for a document"""
    chunks = get_document_chunks(file_path)
    return jsonify(chunks)

@app.route('/api/search')
def api_search():
    """API endpoint for vector search"""
    query = request.args.get('query', '')
    top_k = int(request.args.get('top_k', 5))
    similarity = request.args.get('similarity', 'cosine')
    model = request.args.get('model', 'text-embedding-3-small')
    
    if not query:
        return jsonify({"error": "Query is required"}), 400
    
    try:
        results = vector_search(
            query=query,
            top_k=top_k,
            similarity_metric=similarity,
            model_name=model
        )
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 