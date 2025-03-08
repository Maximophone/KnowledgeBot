"""
Implementation of various chunking strategies.
"""

from typing import List, Optional, Dict, Any, Tuple
from .chunker import ChunkingStrategy, Chunk
from .llm_parser import (
    parse_json_response, 
    validate_chunk_schema,
    extract_chunks_from_markers,
    format_error_message,
    get_expected_schema_example
)
import sys
import os
import json
import logging
import traceback
import math

# Add parent directory to path to allow importing from ai module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai.tokens import n_tokens
from ai.client import AI, DEFAULT_TEMPERATURE
from ai.types import Message, MessageContent


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Approximate characters per token (for estimation purposes)
CHARS_PER_TOKEN = 4


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
                 max_retries=5, fallback=False):
        """
        Initialize the LLM chunker.
        
        Args:
            ai_client: The AI client to use for chunking
            prompt_template: The prompt template to use for the LLM
            model_name: The model to use (defaults to gemini2.0flash)
            max_retries: Maximum number of retry attempts
            fallback: Whether to fall back to SimpleChunker if LLM chunking fails
        """
        logger.info("Initializing LLMChunker")
        
        self.ai_client = ai_client
        self.prompt_path = "ai/chunking/chunking_prompt.md"
        self.model_name = model_name or "gemini2.0flash"
        self.max_retries = max_retries
        self.fallback = fallback
        self.conversation_history = []
        
        # Load prompt template
        if prompt_template is None and self.prompt_path:
            try:
                logger.info(f"Loading prompt template from {self.prompt_path}")
                with open(self.prompt_path, "r", encoding="utf-8") as f:
                    self.prompt_template = f.read()
                logger.debug(f"Prompt template loaded ({len(self.prompt_template)} characters)")
            except Exception as e:
                logger.error(f"Failed to load prompt template: {str(e)}")
                traceback.print_exc()
                raise ValueError(f"Failed to load prompt template from {self.prompt_path}: {str(e)}")
        else:
            self.prompt_template = prompt_template
            
        # Check if prompt template contains required placeholder
        if self.prompt_template and "{max_token_count}" not in self.prompt_template:
            error_msg = "Prompt template does not contain {max_token_count} placeholder"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Initialize AI client
        if self.ai_client is None:
            try:
                logger.info(f"Creating AI client with model {self.model_name}")
                self.ai_client = AI(model_name=self.model_name)
                logger.info(f"AI client initialized successfully")
                # Check if AI client has the expected methods
                if not hasattr(self.ai_client, 'messages'):
                    error_msg = f"AI client does not have 'messages' method. Available methods: {dir(self.ai_client)}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            except Exception as e:
                logger.error(f"Failed to initialize AI client: {str(e)}")
                traceback.print_exc()
                raise
    
    def _create_message(self, text: str, role: str = "user") -> Message:
        """
        Create a message object for the AI conversation.
        
        Args:
            text: The message text
            role: The role of the message sender (user, assistant, system)
            
        Returns:
            Message object
        """
        return Message(
            role=role,
            content=[
                MessageContent(
                    type="text",
                    text=text
                )
            ]
        )
    
    def _calculate_target_chunk_count(self, text: str, max_token_count: Optional[int] = None) -> Optional[str]:
        """
        Calculate a target number of chunks based on document size and max token count. Target is 50% of the max token count.
        
        Args:
            text: The text to chunk
            max_token_count: Maximum token count per chunk
            
        Returns:
            A string describing the target number of chunks, or None if max_token_count is not specified
        """
        if not max_token_count or max_token_count <= 0:
            return None
            
        # Estimate total tokens in the document
        total_tokens = n_tokens(text)
        
        # Calculate estimated number of chunks
        estimated_chunks = total_tokens / (max_token_count * 0.5)
        
        # Adjust for document structure (add 10-20% more chunks for semantic boundaries)
        adjusted_min = math.ceil(estimated_chunks)
        adjusted_max = math.ceil(estimated_chunks * 1.2)
        
        # Handle very small documents
        if adjusted_min == 0:
            return "1 chunk (very small document)"
            
        # For larger documents, provide a range
        if adjusted_min == adjusted_max:
            return f"approximately {adjusted_min} chunks"
        else:
            return f"approximately {adjusted_min}-{adjusted_max} chunks"
    
    def _validate_chunk_sizes(self, chunks: List[Dict[str, Any]], 
                             max_token_count: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Validate that chunks meet size constraints (both upper and lower bounds).
        
        Args:
            chunks: List of extracted chunks
            max_token_count: Maximum token count per chunk
            
        Returns:
            List of error messages for invalid chunks, empty list if all valid
        """
        if not max_token_count or not chunks:
            return []
        
        # Calculate approximate character limits
        max_char_limit = max_token_count * CHARS_PER_TOKEN
        min_char_limit = max(max_token_count * CHARS_PER_TOKEN // 10, 50)  # At least 50 chars
        
        errors = []
        
        # For single chunk case (very small document), skip the lower bound check
        skip_lower_bound = len(chunks) == 1
        
        for chunk in chunks:
            content_length = len(chunk["content"])
            token_estimate = n_tokens(chunk["content"])
            chunk_id = chunk["id"]
            
            # Check upper bound
            if token_estimate > max_token_count or content_length > max_char_limit:
                errors.append({
                    "id": chunk_id,
                    "type": "size_exceeded",
                    "message": f"Chunk {chunk_id} exceeds maximum size: {token_estimate} tokens ({content_length} chars), max allowed: {max_token_count} tokens ({max_char_limit} chars)"
                })
                continue
                
            # Check lower bound (skip for single chunk case)
            if not skip_lower_bound and (token_estimate < max_token_count // 10 or content_length < min_char_limit):
                errors.append({
                    "id": chunk_id,
                    "type": "size_too_small",
                    "message": f"Chunk {chunk_id} is too small: {token_estimate} tokens ({content_length} chars), min recommended: {max_token_count // 10} tokens ({min_char_limit} chars)"
                })
                
        return errors
    
    def _process_llm_response(self, response: str, text: str, 
                             max_token_count: Optional[int] = None,
                             retry_count: int = 0) -> Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Process and validate the LLM response, with retry logic.
        
        Args:
            response: Raw LLM response
            text: Original text being chunked
            max_token_count: Maximum token count per chunk
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
        
        # Collect all validation errors
        all_errors = []
        
        # Extract chunks from markers and collect extraction errors
        successful_chunks, failed_chunks = extract_chunks_from_markers(text, json_data)
        
        # Add extraction errors to all_errors list
        for chunk in failed_chunks:
            all_errors.append({
                "id": chunk["id"],
                "type": "extraction_failed",
                "message": f"Chunk {chunk['id']}: {chunk['error']}"
            })
        
        # Validate chunk sizes if max_token_count is provided
        if max_token_count and successful_chunks:
            size_errors = self._validate_chunk_sizes(successful_chunks, max_token_count)
            all_errors.extend(size_errors)
        
        # If there are any errors (extraction or size), we need to retry
        if all_errors:
            logger.warning(f"Found {len(all_errors)} issues with chunks: "
                          f"{len(failed_chunks)} extraction errors, "
                          f"{len(all_errors) - len(failed_chunks)} size issues.")
            
            if retry_count < self.max_retries:
                # Format error message with all issues
                extraction_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "extraction_failed"])
                size_exceeded_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "size_exceeded"])
                size_too_small_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "size_too_small"])
                
                error_msg = f"""I found {len(all_errors)} issues with your chunking solution that need to be fixed:

"""
                if extraction_errors:
                    error_msg += f"""EXTRACTION ERRORS:
{extraction_errors}

"""
                if size_exceeded_errors:
                    error_msg += f"""SIZE EXCEEDED ERRORS:
{size_exceeded_errors}

"""
                if size_too_small_errors:
                    error_msg += f"""SIZE TOO SMALL ERRORS:
{size_too_small_errors}

"""
                
                error_msg += f"""Please fix ALL these issues and provide a new chunking solution that:
1. Uses exact text markers from the document
2. Ensures no chunk exceeds {max_token_count} tokens ({max_token_count * CHARS_PER_TOKEN} characters)
3. Ensures each chunk is at least {max_token_count // 10} tokens ({max_token_count * CHARS_PER_TOKEN // 10} characters), unless the document is very small
4. Respects semantic boundaries while meeting size constraints

All chunks must be valid for the solution to be accepted.
"""
                return False, None, error_msg
            else:
                return False, None, f"Max retries exceeded. Found {len(all_errors)} issues with chunks."
        
        # If we got this far with no errors, all chunks are valid
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
        logger.info("Starting LLM chunking process")
        logger.info(f"Text length: {len(text)} characters")
        logger.info(f"Max chunk size: {max_chunk_size} tokens (approx. {max_chunk_size * CHARS_PER_TOKEN if max_chunk_size else 'Not specified'} chars)")
        
        # Check if we have a valid AI client
        if self.ai_client is None:
            error_msg = "No AI client available"
            logger.error(error_msg)
            if self.fallback:
                logger.info("Falling back to SimpleChunker")
                simple_chunker = SimpleChunker()
                return simple_chunker.chunk(text, max_chunk_size, overlap, **kwargs)
            else:
                raise ValueError(error_msg)
        
        # Format the system prompt with max token count
        try:
            logger.info("Formatting system prompt with max token count")
            token_value = max_chunk_size if max_chunk_size else "Use your judgment"
            system_prompt = self.prompt_template.format(max_token_count=token_value)
            logger.debug(f"System prompt formatted successfully")
        except Exception as e:
            error_msg = f"Error formatting system prompt: {str(e)}"
            logger.error(error_msg)
            traceback.print_exc()
            raise ValueError(error_msg)
        
        # Reset conversation history
        self.conversation_history = []
        
        # Get the schema example for the reminder
        expected_schema = get_expected_schema_example().strip()
        
        # Calculate size limits for user message
        max_char_limit = "not specified"
        min_char_limit = "not specified"
        if max_chunk_size:
            max_char_limit = f"approximately {max_chunk_size * CHARS_PER_TOKEN} characters"
            min_char_limit = f"approximately {max(max_chunk_size * CHARS_PER_TOKEN // 10, 50)} characters"
            
        # Calculate target chunk count
        target_chunks = self._calculate_target_chunk_count(text, max_chunk_size)
        target_chunks_text = f"\n**LOOSE TARGET: {target_chunks} CHUNKS**" if target_chunks else ""
        
        # Prepare initial message with schema reminder at the end
        user_message = f"""Please analyze and chunk the following document:

```
{text}
```

REMINDER: Your response MUST include valid JSON in this exact format:
```json
{expected_schema}
```

Size requirements:
- Maximum chunk size: {max_chunk_size if max_chunk_size else 'Use your judgment'} tokens ({max_char_limit})
- Minimum recommended chunk size: {max_chunk_size // 10 if max_chunk_size else 'Use your judgment'} tokens ({min_char_limit})
- Exception: If the document is very small, it can be a single chunk below the minimum size{target_chunks_text}

Make sure to:
- Wrap your JSON in ```json and ``` markers
- Ensure your start_text and end_text contain EXACT text from the document
- Respect semantic boundaries (paragraphs, sections) when possible
- Balance chunk sizes to stay within the limits while preserving meaning
"""
        # Add the initial user message to conversation history
        self.conversation_history.append(self._create_message(user_message))
        
        logger.debug("Initial user message prepared")
        
        # Initialize retry counter and result container
        retry_count = 0
        chunks_data = None
        success = False
        
        # Temperature setting
        temperature = kwargs.get('temperature', DEFAULT_TEMPERATURE)
        max_response_tokens = kwargs.get('max_response_tokens', 2048)
        
        while retry_count <= self.max_retries:
            try:
                # Use the 'messages' method with our conversation history
                logger.info(f"Sending request to AI (retry {retry_count}/{self.max_retries})")
                
                ai_response = self.ai_client.messages(
                    messages=self.conversation_history,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_response_tokens
                )
                
                logger.info("Received response from AI")
                response = ai_response.content
                logger.debug(f"AI response received ({len(response) if response else 0} characters)")
                
                # Add the assistant response to the conversation history
                self.conversation_history.append(self._create_message(response, role="assistant"))
                
                # Process the response with size validation
                success, chunks_data, error_msg = self._process_llm_response(
                    response, text, max_chunk_size, retry_count
                )
                
                if success:
                    logger.info("Successfully processed AI response")
                    break
                    
                if retry_count == self.max_retries:
                    logger.warning(f"Max retries exceeded: {error_msg}")
                    break
                    
                # Retry with the error message
                retry_count += 1
                logger.info(f"Retry {retry_count}/{self.max_retries}: {error_msg[:100]}...")
                
                # Add the error feedback to the conversation history
                self.conversation_history.append(self._create_message(error_msg))
            
            except Exception as e:
                error_msg = f"Error during AI interaction: {str(e)}"
                logger.error(error_msg)
                traceback.print_exc()
                
                if retry_count < self.max_retries:
                    retry_count += 1
                    logger.info(f"Retrying after error ({retry_count}/{self.max_retries})")
                    continue
                else:
                    logger.error("Max retries exceeded after error")
                    break
        
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
        
        logger.info(f"LLM chunking completed successfully with {len(chunks)} chunks")
        return chunks 