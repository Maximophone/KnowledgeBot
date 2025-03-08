"""
Tests for the chunking module.
"""

import sys
import os
import unittest

# Add parent directory to path to allow importing
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.chunking import Chunker, SimpleChunker, LLMChunker, Chunk


class TestSimpleChunker(unittest.TestCase):
    """Test cases for SimpleChunker."""
    
    def setUp(self):
        self.text = "This is a test document. It has multiple sentences. " + \
                    "We want to test if the chunking works correctly. " + \
                    "The chunking should split this text into multiple chunks."
        self.chunker = Chunker(SimpleChunker())
    
    def test_basic_chunking(self):
        """Test basic chunking with default settings."""
        chunks = self.chunker.chunk(self.text)
        self.assertEqual(len(chunks), 1, "Text should fit in one chunk by default")
        self.assertEqual(chunks[0].content, self.text)
        
    def test_small_chunks(self):
        """Test chunking with small chunk size."""
        chunk_size = 30
        chunks = self.chunker.chunk(self.text, max_chunk_size=chunk_size)
        
        # Calculate expected number of chunks
        expected_chunks = (len(self.text) + chunk_size - 1) // chunk_size
        self.assertEqual(len(chunks), expected_chunks)
        
        # Check if all chunks have the correct size (except possibly the last one)
        for i in range(len(chunks) - 1):
            self.assertLessEqual(len(chunks[i].content), chunk_size)
        
        # Verify that combined content equals original text
        combined = ''.join(chunk.content for chunk in chunks)
        self.assertEqual(combined, self.text)
    
    def test_overlapping_chunks(self):
        """Test chunking with overlap."""
        chunk_size = 50
        overlap = 10
        chunks = self.chunker.chunk(self.text, max_chunk_size=chunk_size, overlap=overlap)
        
        # Check if chunks overlap correctly
        for i in range(len(chunks) - 1):
            end_text = chunks[i].content[-overlap:]
            start_text = chunks[i+1].content[:overlap]
            self.assertEqual(end_text, start_text)
    
    def test_empty_text(self):
        """Test chunking with empty text."""
        chunks = self.chunker.chunk("")
        self.assertEqual(len(chunks), 0)
    
    def test_token_estimate(self):
        """Test token estimation in metadata."""
        chunks = self.chunker.chunk(self.text)
        for chunk in chunks:
            self.assertIn("token_estimate", chunk.metadata)
            self.assertIsInstance(chunk.metadata["token_estimate"], int)


class TestLLMChunker(unittest.TestCase):
    """Test cases for LLMChunker (basic functionality)."""
    
    def setUp(self):
        self.text = "This is a test document. It has multiple sentences. " + \
                    "We want to test if the chunking works correctly. " + \
                    "The chunking should split this text into multiple chunks."
        self.chunker = Chunker(LLMChunker())
    
    def test_fallback_behavior(self):
        """Test that LLMChunker falls back to SimpleChunker for now."""
        llm_chunks = self.chunker.chunk(self.text, max_chunk_size=30)
        
        # Compare with SimpleChunker
        simple_chunker = Chunker(SimpleChunker())
        simple_chunks = simple_chunker.chunk(self.text, max_chunk_size=30)
        
        self.assertEqual(len(llm_chunks), len(simple_chunks))
        

if __name__ == "__main__":
    unittest.main() 