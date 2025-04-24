"""
Tests for the LLM parser utilities.
"""

import sys
import os
import unittest
import json

# Add parent directory to path to allow importing
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.chunking.llm_parser import (
    extract_json_from_response,
    parse_json_response,
    validate_chunk_schema,
    find_chunk_boundaries,
    extract_chunks_from_markers
)


class TestLLMParser(unittest.TestCase):
    """Test cases for LLM parser utilities."""
    
    def setUp(self):
        # Sample valid chunk data
        self.valid_chunk_data = {
            "chunks": [
                {
                    "id": 1,
                    "metadata": {
                        "topic": "Introduction to chunking",
                        "type": "section"
                    },
                    "start_text": "This is the beginning of the chunk",
                    "end_text": "This is the end of the chunk"
                }
            ]
        }
        
        # Sample text for testing
        self.sample_text = """
        This is a test document.
        
        This is the beginning of the chunk. Here is some content in the middle.
        More content here. This is the end of the chunk.
        
        Some additional text after the chunk.
        """
    
    def test_extract_json_from_response(self):
        """Test extracting JSON from different response formats."""
        # Test with json code block
        response_with_code_block = """
        Here's my analysis of the document:
        
        ```json
        {
            "chunks": [
                {
                    "id": 1,
                    "metadata": {
                        "topic": "Test topic",
                        "type": "section"
                    },
                    "start_text": "Start text",
                    "end_text": "End text"
                }
            ]
        }
        ```
        
        I've split it into semantic units based on the content.
        """
        
        extracted = extract_json_from_response(response_with_code_block)
        self.assertIn('"chunks"', extracted)
        self.assertIn('"id": 1', extracted)
        
        # Test with raw JSON
        raw_json = '{"chunks": [{"id": 1, "metadata": {"topic": "Test", "type": "test"}, "start_text": "Start", "end_text": "End"}]}'
        extracted = extract_json_from_response(raw_json)
        self.assertEqual(raw_json, extracted)
    
    def test_parse_json_response(self):
        """Test parsing JSON responses."""
        # Valid JSON
        valid_response = '{"chunks": [{"id": 1, "metadata": {"topic": "Test", "type": "test"}, "start_text": "Start", "end_text": "End"}]}'
        success, data, error = parse_json_response(valid_response)
        self.assertTrue(success)
        self.assertIsNotNone(data)
        self.assertIsNone(error)
        self.assertIn("chunks", data)
        
        # Invalid JSON
        invalid_response = '{"chunks": [{"id": 1, missing quotes, "start_text": "Start"}]}'
        success, data, error = parse_json_response(invalid_response)
        self.assertFalse(success)
        self.assertEqual({}, data)
        self.assertIsNotNone(error)
    
    def test_validate_chunk_schema(self):
        """Test schema validation."""
        # Valid schema
        valid, error = validate_chunk_schema(self.valid_chunk_data)
        self.assertTrue(valid)
        self.assertIsNone(error)
        
        # Missing required key
        invalid_data = {"not_chunks": []}
        valid, error = validate_chunk_schema(invalid_data)
        self.assertFalse(valid)
        self.assertIn("Missing required key", error)
        
        # Empty chunks array
        invalid_data = {"chunks": []}
        valid, error = validate_chunk_schema(invalid_data)
        self.assertFalse(valid)
        self.assertIn("cannot be empty", error)
        
        # Missing fields in chunk
        invalid_data = {"chunks": [{"id": 1}]}
        valid, error = validate_chunk_schema(invalid_data)
        self.assertFalse(valid)
        self.assertIn("missing required fields", error)
        
        # Wrong type
        invalid_data = {"chunks": [{"id": "string instead of int", "metadata": {}, "start_text": "", "end_text": ""}]}
        valid, error = validate_chunk_schema(invalid_data)
        self.assertFalse(valid)
        self.assertIn("must be an integer", error)
    
    def test_find_chunk_boundaries(self):
        """Test finding chunk boundaries in text."""
        # Valid boundaries
        chunk_markers = {
            "start_text": "This is the beginning of the chunk",
            "end_text": "This is the end of the chunk"
        }
        
        success, start_pos, end_pos, error = find_chunk_boundaries(self.sample_text, chunk_markers)
        self.assertTrue(success)
        self.assertIsNotNone(start_pos)
        self.assertIsNotNone(end_pos)
        self.assertIsNone(error)
        
        # Start marker not found
        invalid_markers = {
            "start_text": "This text does not exist",
            "end_text": "This is the end of the chunk"
        }
        
        success, start_pos, end_pos, error = find_chunk_boundaries(self.sample_text, invalid_markers)
        self.assertFalse(success)
        self.assertIsNone(start_pos)
        self.assertIsNone(end_pos)
        self.assertIn("Could not find start marker", error)
        
        # End marker not found
        invalid_markers = {
            "start_text": "This is the beginning of the chunk",
            "end_text": "This text does not exist"
        }
        
        success, start_pos, end_pos, error = find_chunk_boundaries(self.sample_text, invalid_markers)
        self.assertFalse(success)
        self.assertIsNone(start_pos)
        self.assertIsNone(end_pos)
        self.assertIn("Could not find end marker", error)
    
    def test_extract_chunks_from_markers(self):
        """Test extracting chunks from text using markers."""
        # Create chunk data with markers that exist in the sample text
        chunk_data = {
            "chunks": [
                {
                    "id": 1,
                    "metadata": {
                        "topic": "Test topic",
                        "type": "section"
                    },
                    "start_text": "This is the beginning of the chunk",
                    "end_text": "This is the end of the chunk"
                }
            ]
        }
        
        successful, failed = extract_chunks_from_markers(self.sample_text, chunk_data)
        self.assertEqual(1, len(successful))
        self.assertEqual(0, len(failed))
        self.assertEqual(1, successful[0]["id"])
        self.assertIn("beginning of the chunk", successful[0]["content"])
        self.assertIn("end of the chunk", successful[0]["content"])
        
        # Test with markers that don't exist
        invalid_chunk_data = {
            "chunks": [
                {
                    "id": 1,
                    "metadata": {
                        "topic": "Test topic",
                        "type": "section"
                    },
                    "start_text": "This does not exist",
                    "end_text": "Neither does this"
                }
            ]
        }
        
        successful, failed = extract_chunks_from_markers(self.sample_text, invalid_chunk_data)
        self.assertEqual(0, len(successful))
        self.assertEqual(1, len(failed))
        self.assertEqual(1, failed[0]["id"])
        self.assertIn("error", failed[0])


if __name__ == "__main__":
    unittest.main() 