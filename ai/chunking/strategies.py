"""
Implementation of various chunking strategies.
"""

from typing import List, Optional, Dict, Any, Tuple
from .chunker import ChunkingStrategy, Chunk
from .llm_parser import (
    parse_json_response, 
    validate_chunk_schema,
    extract_chunks_from_markers,
    format_error_message
)
import sys
import os
import json
import logging

# Add parent directory to path to allow importing from ai module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai.tokens import n_tokens
from ai.client import AI, DEFAULT_TEMPERATURE


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleChunker(ChunkingStrategy):
    """
    A simple chunking strategy that divides text into equal-sized chunks.
    This strategy doesn't consider semantic boundaries and simply splits
    by character count.
    """
    
    def chunk(self, text: str, max_chunk_size: Optional[int] = 1000,
              overlap: int = 0, **kwargs) -> List[Chunk]:
        """
        Split text into chunks of equal size.
        
        Args:
            text: The text to chunk
            max_chunk_size: Maximum size of each chunk in characters
            overlap: Number of characters to overlap between chunks
            **kwargs: Additional parameters (ignored in this implementation)
            
        Returns:
            List of Chunk objects
        """
        if max_chunk_size is None:
            max_chunk_size = 1000  # Default chunk size
            
        chunks = []
        text_length = len(text)
        
        if text_length == 0:
            return chunks
            
        # Calculate effective chunk size (accounting for overlap)
        effective_size = max_chunk_size - overlap
        if effective_size <= 0:
            raise ValueError("Overlap must be less than max_chunk_size")
        
        # Create chunks
        position = 0
        chunk_id = 1
        
        while position < text_length:
            # Calculate end position for this chunk
            end_pos = min(position + max_chunk_size, text_length)
            
            # Extract chunk content
            chunk_content = text[position:end_pos]
            
            # Create chunk with metadata
            metadata = {
                "type": "fixed-size",
                "strategy": "simple",
                "char_count": len(chunk_content),
                "token_estimate": n_tokens(chunk_content)
            }
            
            chunk = Chunk(
                id=chunk_id,
                content=chunk_content,
                start_pos=position,
                end_pos=end_pos - 1,  # End position is inclusive
                metadata=metadata
            )
            
            chunks.append(chunk)
            
            # Move position for next chunk, accounting for overlap
            position += effective_size
            chunk_id += 1
            
        return chunks


class LLMChunker(ChunkingStrategy):
    """
    A chunking strategy that uses an LLM to create semantically coherent chunks.
    Leverages AI to identify natural boundaries and semantically meaningful units.
    """
    
    def __init__(self, ai_client=None, prompt_template=None, model_name=None, 
                 max_retries=3, fallback=True):
        """
        Initialize the LLM chunker.
        
        Args:
            ai_client: The AI client to use for chunking
            prompt_template: The prompt template to use for the LLM
            model_name: The model to use (defaults to sonnet3.7)
            max_retries: Maximum number of retry attempts
            fallback: Whether to fall back to SimpleChunker if LLM chunking fails
        """
        self.ai_client = ai_client
        self.prompt_path = "ai/chunking/chunking_prompt.md"
        self.model_name = model_name or "gemini2.0flash"
        self.max_retries = max_retries
        self.fallback = fallback
        
        # Load default prompt if none provided
        if prompt_template is None and self.prompt_path:
            try:
                with open(self.prompt_path, "r", encoding="utf-8") as f:
                    self.prompt_template = f.read()
            except Exception as e:
                logger.error(f"Failed to load prompt template: {str(e)}")
                self.prompt_template = "Please chunk this document into semantically coherent parts."
        else:
            self.prompt_template = prompt_template
            
        # Lazy initialization of AI client
        if self.ai_client is None:
            try:
                # Initialize the AI client with the system prompt from the chunking_prompt.md file
                self.ai_client = AI(model_name=self.model_name)
                logger.info(f"Initialized AI client with model {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize AI client: {str(e)}")
                self.ai_client = None
    
    def _process_llm_response(self, response: str, text: str, retry_count: int = 0) -> Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Process and validate the LLM response, with retry logic.
        
        Args:
            response: Raw LLM response
            text: Original text being chunked
            retry_count: Current retry attempt number
            
        Returns:
            Tuple containing:
                - Success flag (True if processing succeeded)
                - List of extracted chunks or None if failed
                - Error message if failed, None otherwise
        """
        # Parse the JSON response
        success_parse, json_data, parsing_error = parse_json_response(response)
        
        if not success_parse:
            logger.warning(f"Failed to parse JSON: {parsing_error}")
            
            if retry_count < self.max_retries:
                # Retry with error feedback
                error_msg = format_error_message(
                    success_parse=False, 
                    json_data={}, 
                    schema_valid=False,
                    validation_error=None, 
                    parsing_error=parsing_error
                )
                
                return False, None, error_msg
            else:
                return False, None, f"Max retries exceeded. Failed to parse JSON: {parsing_error}"
        
        # Validate the schema
        schema_valid, validation_error = validate_chunk_schema(json_data)
        
        if not schema_valid:
            logger.warning(f"Schema validation failed: {validation_error}")
            
            if retry_count < self.max_retries:
                # Retry with error feedback
                error_msg = format_error_message(
                    success_parse=True, 
                    json_data=json_data, 
                    schema_valid=False,
                    validation_error=validation_error, 
                    parsing_error=None
                )
                
                return False, None, error_msg
            else:
                return False, None, f"Max retries exceeded. Schema validation failed: {validation_error}"
        
        # Extract chunks from markers
        successful_chunks, failed_chunks = extract_chunks_from_markers(text, json_data)
        
        if not successful_chunks:
            logger.warning(f"No chunks were successfully extracted. {len(failed_chunks)} chunks failed extraction.")
            
            if retry_count < self.max_retries:
                error_list = "\n".join([f"- Chunk {c['id']}: {c['error']}" for c in failed_chunks])
                error_msg = f"""
I was able to parse your JSON and it conforms to the schema, but I couldn't extract any chunks from the document using your markers.

Errors:
{error_list}

Please provide more accurate start_text and end_text markers that can be found in the original document.
"""
                return False, None, error_msg
            else:
                return False, None, f"Max retries exceeded. Failed to extract chunks using provided markers."
        
        if failed_chunks:
            logger.warning(f"{len(failed_chunks)} chunks failed extraction. {len(successful_chunks)} chunks were successful.")
        
        return True, successful_chunks, None
    
    def chunk(self, text: str, max_chunk_size: Optional[int] = None,
              overlap: int = 0, **kwargs) -> List[Chunk]:
        """
        Split text into semantically coherent chunks using an LLM.
        
        Args:
            text: The text to chunk
            max_chunk_size: Maximum size of each chunk in tokens
            overlap: Number of tokens to overlap between chunks (not directly used for LLM chunking)
            **kwargs: Additional parameters passed to the LLM
            
        Returns:
            List of Chunk objects
            
        Raises:
            ValueError: If chunking fails and fallback is disabled
        """
        # Check if we have a valid AI client
        if self.ai_client is None:
            logger.warning("No AI client available. Falling back to SimpleChunker.")
            if self.fallback:
                simple_chunker = SimpleChunker()
                return simple_chunker.chunk(text, max_chunk_size, overlap, **kwargs)
            else:
                raise ValueError("No AI client available and fallback is disabled")
        
        # Prepare the system prompt with the max token count
        system_prompt = self.prompt_template
        if max_chunk_size:
            system_prompt = system_prompt.format(max_token_count=max_chunk_size)
        else:
            system_prompt = system_prompt.format(max_token_count="Not specified, use your judgment")
        
        # Prepare a simple user message with just the document to chunk
        user_message = f"""Please analyze and chunk the following document:

```
{text}
```
"""
        
        # Initialize retry counter and result container
        retry_count = 0
        chunks_data = None
        success = False
        
        # Initial request to the LLM
        temperature = kwargs.get('temperature', DEFAULT_TEMPERATURE)
        try:
            # Use the 'message' method with our system prompt and user message
            ai_response = self.ai_client.message(
                message=user_message,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=kwargs.get('max_response_tokens', 2048)
            )
            response = ai_response.content
        except Exception as e:
            logger.error(f"Error calling AI: {str(e)}")
            if self.fallback:
                logger.warning("AI call failed. Falling back to SimpleChunker.")
                simple_chunker = SimpleChunker()
                return simple_chunker.chunk(text, max_chunk_size, overlap, **kwargs)
            else:
                raise ValueError(f"AI call failed: {str(e)}")
        
        while retry_count <= self.max_retries:
            success, chunks_data, error_msg = self._process_llm_response(
                response, text, retry_count
            )
            
            if success:
                break
                
            if retry_count == self.max_retries:
                logger.warning(f"Max retries exceeded: {error_msg}")
                break
                
            # Retry with the error message
            logger.info(f"Retry {retry_count + 1}/{self.max_retries}: {error_msg}")
            try:
                # Use the error message as the new user message for retry
                ai_response = self.ai_client.message(
                    message=error_msg,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=kwargs.get('max_response_tokens', 2048)
                )
                response = ai_response.content
            except Exception as e:
                logger.error(f"Error during retry: {str(e)}")
                break
            
            retry_count += 1
        
        # If LLM chunking failed and fallback is enabled, use SimpleChunker
        if not success and self.fallback:
            logger.warning("LLM chunking failed. Falling back to SimpleChunker.")
            simple_chunker = SimpleChunker()
            return simple_chunker.chunk(text, max_chunk_size, overlap, **kwargs)
        
        # If LLM chunking failed and fallback is disabled, raise an error
        if not success:
            raise ValueError(f"LLM chunking failed after {retry_count} retries.")
        
        # Convert successful chunks to Chunk objects
        chunks = []
        for chunk_data in chunks_data:
            # Add token estimation to metadata
            chunk_data["metadata"]["token_estimate"] = n_tokens(chunk_data["content"])
            chunk_data["metadata"]["strategy"] = "llm"
            
            # Create Chunk object
            chunk = Chunk(
                id=chunk_data["id"],
                content=chunk_data["content"],
                start_pos=chunk_data["start_pos"],
                end_pos=chunk_data["end_pos"],
                metadata=chunk_data["metadata"]
            )
            chunks.append(chunk)
        
        return chunks 