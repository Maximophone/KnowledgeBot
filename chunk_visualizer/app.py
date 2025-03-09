import os
import json
import sqlite3
import base64
from flask import Flask, render_template, request, jsonify
from pathlib import Path

app = Flask(__name__)

# Default path to vector database
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                              'data', 'vector_db.sqlite')

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

if __name__ == '__main__':
    app.run(debug=True) 