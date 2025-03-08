"""
Vector database module for efficient storage and retrieval of embeddings.
"""

# Import the module using a relative path that works in various contexts
import os
import sys

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add to sys.path for local imports
sys.path.insert(0, current_dir)

# Import the VectorDB class directly from the file
from vector_db import VectorDB

__all__ = ['VectorDB'] 