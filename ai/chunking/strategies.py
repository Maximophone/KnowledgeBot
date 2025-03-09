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
import re
import time

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
                 max_retries=5, fallback=False, max_direct_tokens=1000):
        """
        Initialize the LLM chunker.
        
        Args:
            ai_client: The AI client to use for chunking
            prompt_template: The prompt template to use for the LLM
            model_name: The model to use (defaults to gemini2.0flash)
            max_retries: Maximum number of retry attempts
            fallback: Whether to fall back to SimpleChunker if LLM chunking fails
            max_direct_tokens: Maximum token count for direct chunking (larger documents use recursive approach)
        """
        logger.info("Initializing LLMChunker")
        
        self.ai_client = ai_client
        self.prompt_path = "ai/chunking/chunking_prompt.md"
        self.model_name = model_name or "gemini2.0flash"
        self.max_retries = max_retries
        self.fallback = fallback
        self.conversation_history = []
        self.max_direct_tokens = max_direct_tokens
        
        # Track all splitting conversations
        self.split_conversations = []
        
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
                self.ai_client = AI(model_name=self.model_name, rate_limiting=True)
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
        Calculate a target number of chunks based on document size and max token count.
        
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
        estimated_chunks = total_tokens / max_token_count
        
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
    
    def _find_split_point(self, text: str, retry_count: int = 0, 
                         depth: int = 0, part: str = "document") -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Ask the LLM to find a good semantic split point in the document, ideally near the middle.
        
        Args:
            text: The text to split
            retry_count: Current retry attempt number
            depth: Current recursion depth for tracking purposes
            part: Description of which part is being split (for tracking)
            
        Returns:
            Tuple containing:
                - Success flag (True if split point found)
                - Split position or None if failed
                - Error message if failed, None otherwise
        """
        logger.info(f"Finding semantic split point (retry {retry_count}/{self.max_retries})")
        
        # Create a new conversation for this split point determination
        split_conversation = []
        
        # System prompt for document splitting
        system_prompt = """You are DocSplitter-2025, an expert system for finding optimal split points in documents.
Your task is to find the most logical and semantically coherent place to split a document into two parts.

RULES:
1. Choose a split point that respects the document's structure (section boundaries, paragraph breaks)
2. The split point should be approximately in the middle of the document
3. Never split in the middle of a sentence, word, or logical unit
4. Prefer splitting between major sections or at clear topic transitions
5. First explain your strategy, then output ONLY the exact text between BEGIN_SPLIT_POINT and END_SPLIT_POINT markers"""
        
        # Prepare the user message
        user_message = f"""Please analyze this document and find the best place to split it into two parts.
The split should occur at a natural boundary (paragraph break, section end) near the middle of the document.

Document to split:
```
{text}
```

First, briefly explain your strategy for selecting the split point.

Then, provide ONLY the exact text where the first part should end, placing it between BEGIN_SPLIT_POINT and END_SPLIT_POINT markers, like this:

BEGIN_SPLIT_POINT
The exact text from the document where you want to split
END_SPLIT_POINT

IMPORTANT GUIDELINES:
1. Split the document as close to the MIDDLE as possible (50/50 division is ideal)
2. Choose a natural boundary like a paragraph end or section break
3. The text between the markers must be EXACTLY as it appears in the document
4. A moderate length of text (50-100 characters) works best for accurate matching
5. Only the content between the markers will be used for splitting"""
        
        # Create user message object
        user_message_obj = self._create_message(user_message)
        
        # Add to the conversation for this split
        split_conversation.append(user_message_obj)
        
        try:
            # Send request to AI
            ai_response = self.ai_client.messages(
                messages=[user_message_obj],  # Use only this message to avoid conversation history issues
                system_prompt=system_prompt,
                temperature=0.2,  # Lower temperature for more deterministic results
            )
            
            # Get the response text
            full_response = ai_response.content.strip()
            logger.debug(f"AI full response: {full_response}")
            
            # Extract just the split point text from between the markers
            split_pattern = re.compile(r'BEGIN_SPLIT_POINT\s*(.*?)\s*END_SPLIT_POINT', re.DOTALL)
            match = split_pattern.search(full_response)
            
            if match:
                response = match.group(1).strip()
                logger.info(f"Extracted split point text: {response}")
            else:
                # If markers aren't found, treat the entire response as potential split point
                # (this is a fallback for when the model ignores the marker instructions)
                response = full_response
                logger.warning(f"Split point markers not found, using entire response")
            
            # Create assistant message object and add to conversation
            assistant_message_obj = self._create_message(full_response, role="assistant")
            split_conversation.append(assistant_message_obj)
            
            # Store metadata about this split operation
            split_metadata = {
                "timestamp": time.time(),
                "depth": depth,
                "part": part,
                "retry": retry_count,
                "text_length": len(text),
                "token_estimate": n_tokens(text),
                "extracted_split_point": response,
                "full_response": full_response
            }
            
            # Add this complete conversation to the list of splitting conversations
            self.split_conversations.append({
                "metadata": split_metadata,
                "conversation": split_conversation
            })
            
            # Find this text in the document
            split_pos = text.find(response)
            
            if split_pos == -1:
                # Try to find it with flexible whitespace
                # Replace multiple whitespace with \s+ in regex
                flexible_pattern = re.sub(r'\s+', r'\\s+', re.escape(response))
                match = re.search(flexible_pattern, text)
                
                if match:
                    # Found with flexible whitespace
                    split_pos = match.end()
                    logger.info(f"Found split point with flexible whitespace matching at position {split_pos}")
                else:
                    # Not found even with flexible matching
                    if retry_count < self.max_retries:
                        error_msg = f"""I couldn't find the exact text you provided in the document. 
Please ensure you're returning text that exists EXACTLY in the document between the BEGIN_SPLIT_POINT and END_SPLIT_POINT markers.

Your extracted split point: "{response}"

If this was not what you intended, please check your formatting. Your response must include:

BEGIN_SPLIT_POINT
Exact text from the document
END_SPLIT_POINT

Try again and make sure the text appears word-for-word in the document."""
                        logger.warning(f"Split point not found: {response}")
                        
                        # Add error message to conversation history for this split
                        error_message_obj = self._create_message(error_msg)
                        split_conversation.append(error_message_obj)
                        
                        # Update this conversation in the list
                        self.split_conversations[-1]["conversation"] = split_conversation
                        
                        # Try again with feedback
                        return self._find_split_point(text, retry_count + 1, depth, part)
                    else:
                        return False, None, f"Failed to find split point after {self.max_retries} retries."
            else:
                # Add the length of the response to get the end position
                split_pos += len(response)
                logger.info(f"Found split point at position {split_pos}")
            
            return True, split_pos, None
        
        except Exception as e:
            error_msg = f"Error during split point finding: {str(e)}"
            logger.error(error_msg)
            traceback.print_exc()
            
            # Add error to conversation history
            error_message_obj = self._create_message(f"ERROR: {error_msg}", role="system")
            split_conversation.append(error_message_obj)
            
            # Add this failed conversation to the history
            split_metadata = {
                "timestamp": time.time(),
                "depth": depth,
                "part": part,
                "retry": retry_count,
                "text_length": len(text),
                "token_estimate": n_tokens(text),
                "error": str(e)
            }
            
            self.split_conversations.append({
                "metadata": split_metadata,
                "conversation": split_conversation
            })
            
            if retry_count < self.max_retries:
                return self._find_split_point(text, retry_count + 1, depth, part)
            else:
                return False, None, error_msg
    
    def _recursive_chunk(self, text: str, max_chunk_size: Optional[int] = None,
                        position_offset: int = 0, chunk_id_offset: int = 0,
                        depth: int = 0, **kwargs) -> Tuple[bool, List[Chunk], Optional[str]]:
        """
        Recursively chunk a document by splitting it into smaller parts.
        
        Args:
            text: The text to chunk
            max_chunk_size: Maximum size of each chunk in tokens
            position_offset: Offset to add to positions (for recursive calls)
            chunk_id_offset: Offset to add to chunk IDs (for recursive calls)
            depth: Current recursion depth
            **kwargs: Additional parameters passed to the LLM
            
        Returns:
            Tuple containing:
                - Success flag (True if chunking succeeded)
                - List of chunks or empty list if failed
                - Error message if failed, None otherwise
        """
        # Check if the document is small enough for direct chunking
        doc_token_count = n_tokens(text)
        logger.info(f"Recursive chunking at depth {depth}: {len(text)} chars, ~{doc_token_count} tokens")
        
        if doc_token_count <= self.max_direct_tokens:
            logger.info(f"Document is small enough for direct chunking ({doc_token_count} <= {self.max_direct_tokens} tokens)")
            # Directly chunk this part
            success, chunks, error_msg = self._direct_chunk(
                text=text,
                max_chunk_size=max_chunk_size,
                position_offset=position_offset,
                chunk_id_offset=chunk_id_offset,
                **kwargs
            )
            
            return success, chunks, error_msg
        
        # Document is too large, split it
        logger.info(f"Document is too large for direct chunking ({doc_token_count} > {self.max_direct_tokens} tokens)")
        part_description = f"depth_{depth}" if depth == 0 else f"depth_{depth}_offset_{position_offset}"
        success, split_pos, error_msg = self._find_split_point(text, depth=depth, part=part_description)
        
        if not success:
            logger.error(f"Failed to find split point: {error_msg}")
            # If we can't split, try direct chunking as a last resort
            logger.warning("Attempting direct chunking as fallback")
            return self._direct_chunk(
                text=text,
                max_chunk_size=max_chunk_size,
                position_offset=position_offset,
                chunk_id_offset=chunk_id_offset,
                **kwargs
            )
        
        logger.info(f"Splitting document at position {split_pos}")
        
        # Split the document
        left_text = text[:split_pos]
        right_text = text[split_pos:]
        
        # Check if either part is empty (shouldn't happen with a good split point)
        if not left_text or not right_text:
            logger.error("Split resulted in an empty part")
            return False, [], "Split resulted in an empty part"
        
        # Recursively process left part
        left_success, left_chunks, left_error = self._recursive_chunk(
            text=left_text,
            max_chunk_size=max_chunk_size,
            position_offset=position_offset,
            chunk_id_offset=chunk_id_offset,
            depth=depth + 1,
            **kwargs
        )
        
        if not left_success:
            return False, [], f"Failed to chunk left part: {left_error}"
        
        # Recursively process right part
        right_success, right_chunks, right_error = self._recursive_chunk(
            text=right_text,
            max_chunk_size=max_chunk_size,
            position_offset=position_offset + len(left_text),
            chunk_id_offset=chunk_id_offset + len(left_chunks),
            depth=depth + 1,
            **kwargs
        )
        
        if not right_success:
            return False, [], f"Failed to chunk right part: {right_error}"
        
        # Combine the chunks from both parts
        all_chunks = left_chunks + right_chunks
        logger.info(f"Combined {len(left_chunks)} left chunks and {len(right_chunks)} right chunks")
        
        return True, all_chunks, None
    
    def _direct_chunk(self, text: str, max_chunk_size: Optional[int] = None,
                     position_offset: int = 0, chunk_id_offset: int = 0,
                     **kwargs) -> Tuple[bool, List[Chunk], Optional[str]]:
        """
        Directly chunk a document using the LLM (non-recursive approach).
        
        Args:
            text: The text to chunk
            max_chunk_size: Maximum size of each chunk in tokens
            position_offset: Offset to add to positions (for recursive calls)
            chunk_id_offset: Offset to add to chunk IDs (for recursive calls)
            **kwargs: Additional parameters passed to the LLM
            
        Returns:
            Tuple containing:
                - Success flag (True if chunking succeeded)
                - List of chunks or empty list if failed
                - Error message if failed, None otherwise
        """
        logger.info(f"Starting direct LLM chunking process")
        logger.info(f"Text length: {len(text)} characters")
        logger.info(f"Max chunk size: {max_chunk_size} tokens (approx. {max_chunk_size * CHARS_PER_TOKEN if max_chunk_size else 'Not specified'} chars)")
        
        # Check if the text is small enough to be a single chunk
        if max_chunk_size is not None:
            text_token_count = n_tokens(text)
            
            if text_token_count <= max_chunk_size:
                logger.info(f"Text is small enough to be a single chunk ({text_token_count} <= {max_chunk_size} tokens), skipping LLM call")
                
                # Create a single chunk containing the entire text
                chunk = Chunk(
                    id=1 + chunk_id_offset,
                    content=text,
                    start_pos=0 + position_offset,
                    end_pos=len(text) - 1 + position_offset,  # End position is inclusive
                    metadata={
                        "strategy": "llm_single",
                        "type": "single-chunk",
                        "token_estimate": text_token_count,
                        "reason": "Text smaller than max_chunk_size"
                    }
                )
                
                # Return success with a single chunk
                return True, [chunk], None
        
        # Check if we have a valid AI client
        if self.ai_client is None:
            error_msg = "No AI client available"
            logger.error(error_msg)
            return False, [], error_msg
        
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
            return False, [], error_msg
        
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
        target_chunks_text = f"\nTarget: {target_chunks}" if target_chunks else ""
        
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

Coverage requirements:
- Your chunks MUST cover the ENTIRE document with no gaps
- Every non-whitespace character in the document must be included in exactly one chunk
- Ensure your start_text and end_text markers form a continuous sequence when put together

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
        
        if not success:
            return False, [], f"LLM chunking failed after {retry_count} retries: {error_msg}"
        
        # Convert successful chunks to Chunk objects and apply offsets
        chunks = []
        for chunk_data in chunks_data:
            # Add token estimation to metadata
            chunk_data["metadata"]["token_estimate"] = n_tokens(chunk_data["content"])
            chunk_data["metadata"]["strategy"] = "llm"
            
            # Create Chunk object with adjusted positions and IDs
            chunk = Chunk(
                id=chunk_data["id"] + chunk_id_offset,
                content=chunk_data["content"],
                start_pos=chunk_data["start_pos"] + position_offset,
                end_pos=chunk_data["end_pos"] + position_offset,
                metadata=chunk_data["metadata"]
            )
            chunks.append(chunk)
        
        logger.info(f"Direct LLM chunking completed successfully with {len(chunks)} chunks")
        return True, chunks, None
    
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
        successful_chunks, failed_chunks, coverage_error = extract_chunks_from_markers(text, json_data)
        
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
        
        # Check for coverage errors - if all extraction and size checks passed but there are gaps
        if not all_errors and coverage_error:
            all_errors.append({
                "id": 0,  # Coverage is a global issue, not specific to a chunk
                "type": "coverage_incomplete",
                "message": coverage_error
            })
        
        # If there are any errors (extraction, size, or coverage), we need to retry
        if all_errors:
            logger.warning(f"Found {len(all_errors)} issues with chunks")
            
            extraction_errors_count = len([e for e in all_errors if e["type"] == "extraction_failed"])
            size_errors_count = len([e for e in all_errors if e["type"] in ["size_exceeded", "size_too_small"]])
            coverage_errors_count = len([e for e in all_errors if e["type"] == "coverage_incomplete"])
            
            logger.warning(f"Issues breakdown: {extraction_errors_count} extraction errors, "
                          f"{size_errors_count} size issues, "
                          f"{coverage_errors_count} coverage problems.")
            
            if retry_count < self.max_retries:
                # Format error message with all issues
                extraction_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "extraction_failed"])
                size_exceeded_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "size_exceeded"])
                size_too_small_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "size_too_small"])
                coverage_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "coverage_incomplete"])
                
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
                if coverage_errors:
                    error_msg += f"""COVERAGE ERRORS:
{coverage_errors}

"""
                
                error_msg += f"""Please fix ALL these issues and provide a new chunking solution that:
1. Uses exact text markers from the document
2. Ensures no chunk exceeds {max_token_count} tokens ({max_token_count * CHARS_PER_TOKEN} characters)
3. Ensures each chunk is at least {max_token_count // 10} tokens ({max_token_count * CHARS_PER_TOKEN // 10} characters), unless the document is very small
4. Ensures the entire document is covered (no gaps between chunks)
5. Respects semantic boundaries while meeting size constraints

All chunks must be valid and the entire document must be covered for the solution to be accepted.
"""
                return False, None, error_msg
            else:
                return False, None, f"Max retries exceeded. Found {len(all_errors)} issues with chunks."
        
        # If we got this far with no errors, all chunks are valid and cover the entire document
        return True, successful_chunks, None
    
    def chunk(self, text: str, max_chunk_size: Optional[int] = None,
              overlap: int = 0, **kwargs) -> List[Chunk]:
        """
        Split text into semantically coherent chunks using an LLM.
        For large documents, uses a recursive divide-and-conquer approach.
        
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
        logger.info(f"Max direct tokens: {self.max_direct_tokens}")
        
        # Reset histories for a new chunking operation
        self.conversation_history = []
        self.split_conversations = []
        
        # Check if text is empty
        if not text:
            logger.info("Empty text, returning empty chunks list")
            return []
        
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
        
        # Choose strategy based on document size
        doc_token_count = n_tokens(text)
        logger.info(f"Document token count: approximately {doc_token_count} tokens")
        
        if doc_token_count <= self.max_direct_tokens:
            # Use direct chunking for small documents
            logger.info(f"Using direct chunking approach (document size <= {self.max_direct_tokens} tokens)")
            success, chunks, error = self._direct_chunk(text, max_chunk_size, **kwargs)
        else:
            # Use recursive chunking for large documents
            logger.info(f"Using recursive chunking approach (document size > {self.max_direct_tokens} tokens)")
            success, chunks, error = self._recursive_chunk(text, max_chunk_size, **kwargs)
        
        # If chunking failed and fallback is enabled, use SimpleChunker
        if not success and self.fallback:
            logger.warning(f"LLM chunking failed: {error}. Falling back to SimpleChunker.")
            simple_chunker = SimpleChunker()
            return simple_chunker.chunk(text, max_chunk_size, overlap, **kwargs)
        
        # If chunking failed and fallback is disabled, raise an error
        if not success:
            raise ValueError(f"LLM chunking failed: {error}")
        
        logger.info(f"LLM chunking completed successfully with {len(chunks)} chunks")
        return chunks 