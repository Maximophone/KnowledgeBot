"""
Dynamic import module that fixes the circular import issue with vector_db.

This works by:
1. Temporarily patching sys.modules to break the circular import
2. Importing directly from the vector_db.py file
3. Importing other needed components
"""

import os
import sys
import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

# Get paths
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
vector_db_dir = os.path.join(base_dir, 'vector_db')

# Add parent directory to sys.path
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# Add vector_db directory to sys.path
if vector_db_dir not in sys.path:
    sys.path.insert(0, vector_db_dir)

# Create a helper function to import directly from the vector_db directory
def import_vector_db_modules():
    """Import and return the needed modules from vector_db."""
    
    # Create a mock module to prevent circular imports
    class MockModule(ModuleType):
        """A mock module to prevent circular imports."""
        def __init__(self, name):
            super().__init__(name)
            self.VectorDB = None  # Will be replaced later
    
    # Save the original module if it exists
    original_module = sys.modules.get('vector_db', None)
    
    # Replace with our mock module
    mock_module = MockModule('vector_db')
    sys.modules['vector_db'] = mock_module
    
    try:
        # Import the actual modules directly
        storage_spec = importlib.util.spec_from_file_location(
            "vector_db.storage", os.path.join(vector_db_dir, "storage.py")
        )
        storage_module = importlib.util.module_from_spec(storage_spec)
        storage_spec.loader.exec_module(storage_module)
        
        similarity_spec = importlib.util.spec_from_file_location(
            "vector_db.similarity", os.path.join(vector_db_dir, "similarity.py")
        )
        similarity_module = importlib.util.module_from_spec(similarity_spec)
        similarity_spec.loader.exec_module(similarity_module)
        
        # Now import vector_db.py
        vector_db_spec = importlib.util.spec_from_file_location(
            "vector_db.vector_db", os.path.join(vector_db_dir, "vector_db.py")
        )
        vector_db_module = importlib.util.module_from_spec(vector_db_spec)
        
        # Set up the module context
        vector_db_module.storage = storage_module
        vector_db_module.similarity = similarity_module
        vector_db_module.VectorStorage = storage_module.VectorStorage
        vector_db_module.VectorSearcher = similarity_module.VectorSearcher
        vector_db_module.SimilarityMetric = similarity_module.SimilarityMetric
        vector_db_module.CosineSimilarity = similarity_module.CosineSimilarity
        
        # Execute the module
        vector_db_spec.loader.exec_module(vector_db_module)
        
        # Update our mock with the real VectorDB class
        mock_module.VectorDB = vector_db_module.VectorDB
        
        return {
            'VectorDB': vector_db_module.VectorDB,
            'CosineSimilarity': similarity_module.CosineSimilarity,
            'EuclideanDistance': similarity_module.EuclideanDistance, 
            'DotProductSimilarity': similarity_module.DotProductSimilarity,
        }
        
    finally:
        # Restore the original module if it existed
        if original_module:
            sys.modules['vector_db'] = original_module

# Import the modules we need
imported_modules = import_vector_db_modules()
VectorDB = imported_modules['VectorDB']
CosineSimilarity = imported_modules['CosineSimilarity']
EuclideanDistance = imported_modules['EuclideanDistance']
DotProductSimilarity = imported_modules['DotProductSimilarity'] 