"""
Utilities for parsing and validating LLM responses for document chunking.
"""

import json
import re
from typing import Dict, List, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

def extract_json_from_response(response: str) -> str:
    """
    Extract JSON content from an LLM response that might contain explanatory text.
    
    Args:
        response: Raw LLM response text
        
    Returns:
        Extracted JSON string
        
    Raises:
        ValueError: If no JSON content can be found
    """
    # Try to find JSON content enclosed in triple backticks with 'json' language tag
    json_pattern = r"```json\s*([\s\S]*?)\s*```"
    match = re.search(json_pattern, response)
    
    if match:
        return match.group(1).strip()
    
    # Try to find any content enclosed in triple backticks
    backtick_pattern = r"```\s*([\s\S]*?)\s*```"
    match = re.search(backtick_pattern, response)
    
    if match:
        return match.group(1).strip()
    
    # Try to find JSON-like content (starting with { and ending with })
    bracket_pattern = r"(\{[\s\S]*\})"
    match = re.search(bracket_pattern, response)
    
    if match:
        return match.group(1).strip()
    
    # If no JSON-like content found, return the response as is
    # (will likely fail in parse_json_response, but we'll handle that)
    return response


def parse_json_response(response: str) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Parse JSON from an LLM response.
    
    Args:
        response: Raw LLM response text
        
    Returns:
        Tuple containing:
            - Success flag (True if parsing succeeded)
            - Parsed JSON object or empty dict if failed
            - Error message if failed, None otherwise
    """
    json_str = extract_json_from_response(response)
    
    try:
        data = json.loads(json_str)
        return True, data, None
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON: {str(e)}"
        return False, {}, error_msg


def validate_chunk_schema(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate that the parsed JSON conforms to our expected chunk schema.
    
    Args:
        data: Parsed JSON data
        
    Returns:
        Tuple containing:
            - Success flag (True if validation succeeded)
            - Error message if failed, None otherwise
    """
    # Check for required top-level key
    if not isinstance(data, dict):
        return False, "Expected JSON object but got a different type"
        
    if "chunks" not in data:
        return False, "Missing required key 'chunks'"
    
    if not isinstance(data["chunks"], list):
        return False, "'chunks' must be an array"
    
    if not data["chunks"]:
        return False, "'chunks' array cannot be empty"
    
    # Validate each chunk
    for i, chunk in enumerate(data["chunks"]):
        # Check required fields
        missing_fields = []
        for field in ["id", "metadata", "start_text", "end_text"]:
            if field not in chunk:
                missing_fields.append(field)
        
        if missing_fields:
            return False, f"Chunk at index {i} is missing required fields: {', '.join(missing_fields)}"
        
        # Validate field types
        if not isinstance(chunk["id"], int):
            return False, f"Chunk at index {i}: 'id' must be an integer"
        
        if not isinstance(chunk["metadata"], dict):
            return False, f"Chunk at index {i}: 'metadata' must be an object"
            
        if not isinstance(chunk["start_text"], str):
            return False, f"Chunk at index {i}: 'start_text' must be a string"
            
        if not isinstance(chunk["end_text"], str):
            return False, f"Chunk at index {i}: 'end_text' must be a string"
        
        # Check metadata fields
        metadata = chunk["metadata"]
        if "topic" not in metadata:
            return False, f"Chunk at index {i}: metadata is missing 'topic' field"
            
        if "type" not in metadata:
            return False, f"Chunk at index {i}: metadata is missing 'type' field"
    
    return True, None


def find_chunk_boundaries(text: str, chunk_markers: Dict[str, Any]) -> Tuple[bool, Optional[int], Optional[int], Optional[str]]:
    """
    Find the start and end positions of a chunk in the text using start_text and end_text markers.
    Handles start and end markers separately, with truncation as a fallback for each.
    
    Args:
        text: The full text to search in
        chunk_markers: Dict containing 'start_text' and 'end_text' markers
        
    Returns:
        Tuple containing:
            - Success flag (True if boundaries found)
            - Start position (or None if not found)
            - End position (or None if not found)
            - Error message if failed, None otherwise
    """
    start_text = chunk_markers["start_text"]
    end_text = chunk_markers["end_text"]
    chunk_id = chunk_markers["id"]
    
    # ----- STEP 1: Find the start marker -----
    start_pos = None
    
    # First try: Exact start marker
    exact_start_pos = text.find(start_text)
    if exact_start_pos != -1:
        # Found exact start marker
        start_pos = exact_start_pos
        start_len = len(start_text)
        logger.debug(f"Found exact start marker for chunk {chunk_id}")
    else:
        # Second try: Truncated start marker (first 60 chars)
        truncated_start = start_text[:min(60, len(start_text))]
        
        # Skip truncation if the marker is already short
        if len(truncated_start) == len(start_text):
            return False, None, None, f"Could not find start marker for chunk {chunk_id}: '{start_text}'"
        
        truncated_start_pos = text.find(truncated_start)
        if truncated_start_pos != -1:
            # Found truncated start marker
            start_pos = truncated_start_pos
            start_len = len(truncated_start)
            logger.info(f"Using truncated start marker for chunk {chunk_id}: '{truncated_start}'")
        else:
            # Failed to find start marker (both exact and truncated)
            return False, None, None, f"Could not find start marker for chunk {chunk_id}: '{start_text}' (truncated: '{truncated_start}')"
    
    # ----- STEP 2: Find the end marker -----
    # Only search for end marker after the start marker
    search_start = start_pos + start_len
    end_pos = None
    
    # First try: Exact end marker
    exact_end_pos = text[search_start:].find(end_text)
    if exact_end_pos != -1:
        # Found exact end marker
        end_pos = search_start + exact_end_pos + len(end_text)
        logger.debug(f"Found exact end marker for chunk {chunk_id}")
    else:
        # Second try: Truncated end marker (last 60 chars)
        truncated_end = end_text[-min(60, len(end_text)):]
        
        # Skip truncation if the marker is already short
        if len(truncated_end) == len(end_text):
            return False, None, None, f"Could not find end marker for chunk {chunk_id}: '{end_text}'"
        
        truncated_end_pos = text[search_start:].find(truncated_end)
        if truncated_end_pos != -1:
            # Found truncated end marker
            end_pos = search_start + truncated_end_pos + len(truncated_end)
            logger.info(f"Using truncated end marker for chunk {chunk_id}: '{truncated_end}'")
        else:
            # Failed to find end marker (both exact and truncated)
            return False, None, None, f"Could not find end marker for chunk {chunk_id}: '{end_text}' (truncated: '{truncated_end}')"
    
    # Success! Found both markers
    return True, start_pos, end_pos, None


def extract_chunks_from_markers(text: str, chunk_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract chunks from text using the markers provided by the LLM.
    
    Args:
        text: The full text to chunk
        chunk_data: The validated chunk data from the LLM
        
    Returns:
        Tuple containing:
            - List of successfully extracted chunks with content
            - List of failed chunks with error messages
    """
    successful_chunks = []
    failed_chunks = []
    
    for chunk_info in chunk_data["chunks"]:
        # Find the chunk boundaries
        success, start_pos, end_pos, error_msg = find_chunk_boundaries(text, chunk_info)
        
        if not success:
            # Add to failed chunks list
            failed_chunks.append({
                "id": chunk_info["id"],
                "metadata": chunk_info["metadata"],
                "error": error_msg
            })
            continue
        
        # Extract the chunk content
        chunk_content = text[start_pos:end_pos]
        
        # Create a successful chunk entry
        chunk_entry = {
            "id": chunk_info["id"],
            "content": chunk_content,
            "start_pos": start_pos,
            "end_pos": end_pos - 1,  # End position is inclusive in our Chunk class
            "metadata": chunk_info["metadata"]
        }
        successful_chunks.append(chunk_entry)
    
    return successful_chunks, failed_chunks


def get_expected_schema_example() -> str:
    """
    Get an example of the expected JSON schema in string format.
    
    Returns:
        A string containing an example of the expected schema
    """
    return """
{
  "chunks": [
    {
      "id": 1,
      "metadata": {
        "topic": "Brief description of chunk content",
        "type": "section|paragraph|list|code|etc"
      },
      "start_text": "First 50-70 characters of the chunk",
      "end_text": "Last 50-70 characters of the chunk"
    },
    {
      "id": 2,
      "metadata": {
        "topic": "Next chunk topic description",
        "type": "section|paragraph|list|code|etc"
      },
      "start_text": "First 50-70 characters of this chunk",
      "end_text": "Last 50-70 characters of this chunk"
    }
  ]
}
"""


def format_error_message(success_parse: bool, json_data: Dict[str, Any], 
                        schema_valid: bool, validation_error: Optional[str], 
                        parsing_error: Optional[str]) -> str:
    """
    Format an error message to send back to the LLM during retry.
    
    Args:
        success_parse: Whether JSON parsing was successful
        json_data: The parsed JSON data (or empty dict if parsing failed)
        schema_valid: Whether the schema validation was successful
        validation_error: The validation error message, if any
        parsing_error: The JSON parsing error message, if any
        
    Returns:
        Formatted error message for the LLM
    """
    # Get the expected schema example
    expected_schema = get_expected_schema_example()
    
    if not success_parse:
        return f"""
I was unable to parse the JSON in your previous response.

Error details: {parsing_error}

You MUST follow these requirements:
1. Your response MUST contain valid JSON
2. The JSON must be properly formatted without syntax errors
3. Include the JSON within ```json and ``` markers
4. Follow the EXACT schema specified with all required fields

Here is the exact schema your JSON must follow:
```json
{expected_schema.strip()}
```

Please try again with a valid JSON object that follows this structure exactly.
Ensure your response begins with a brief explanation of your chunking strategy, followed by the JSON wrapped in ```json markers.
"""
    
    if not schema_valid:
        return f"""
I was able to parse your JSON, but it doesn't conform to the expected schema.

Error details: {validation_error}

Your JSON must follow this exact schema:
```json
{expected_schema.strip()}
```

Critical requirements:
- The "chunks" array MUST contain at least one chunk
- Every chunk MUST have: id, metadata (with topic and type), start_text, and end_text
- The start_text and end_text fields MUST contain actual text from the document
- The id field MUST be a number
- The metadata must include "topic" and "type" fields

Please fix your response to follow these requirements exactly.
"""
    
    return "Your response is valid, but something else went wrong." 