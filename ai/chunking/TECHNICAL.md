# LLMChunker Technical Documentation

## Overview

The `LLMChunker` is an advanced document chunking system that leverages Large Language Models (LLMs) to create semantically coherent chunks from text documents. It implements a recursive divide-and-conquer approach for handling documents of any size, with robust error handling and validation mechanisms.

## Architecture

### Core Components

1. **LLMChunker Class**: Main implementation of the chunking strategy.
2. **Chunking Methods**:
   - `chunk()`: Primary entry point and dispatcher
   - `_direct_chunk()`: Handles smaller documents directly with LLM
   - `_recursive_chunk()`: Breaks larger documents into smaller parts
   - `_find_split_point()`: Uses LLM to find semantic split points
3. **Validation & Processing**:
   - `_process_llm_response()`: Validates and processes LLM responses
   - `_validate_chunk_sizes()`: Enforces size constraints on chunks
4. **Conversation Tracking**:
   - `conversation_history`: Records chunking-related conversations
   - `split_conversations`: Records all document splitting conversations

## Chunking Process

### 1. Initial Document Assessment

When the `chunk()` method is called, the system:
1. Estimates the token count of the input document
2. Compares it against the `max_direct_tokens` threshold
3. Decides whether to use direct chunking or recursive chunking

```python
# Size-based routing logic in chunk()
if doc_token_count <= self.max_direct_tokens:
    # Use direct chunking for small documents
    success, chunks, error = self._direct_chunk(text, max_chunk_size, **kwargs)
else:
    # Use recursive chunking for large documents
    success, chunks, error = self._recursive_chunk(text, max_chunk_size, **kwargs)
```

### 2. Direct Chunking Process

For documents below the `max_direct_tokens` threshold:

1. **Size Check**: If text is smaller than `max_chunk_size`, it's returned as a single chunk without calling the LLM.
2. **LLM Prompt Construction**: Creates a prompt with the document and chunking requirements.
3. **LLM Interaction**: Sends the prompt to the LLM and receives a JSON response with chunk markers.
4. **Extraction & Validation**: Extracts chunks from the document using markers and validates them.
5. **Retry Mechanism**: If validation fails, provides feedback to the LLM and retries.

### 3. Recursive Chunking Process

For documents above the `max_direct_tokens` threshold:

1. **Split Point Finding**: Uses the LLM to find a semantically appropriate midpoint.
2. **Document Division**: Splits the document at the identified point.
3. **Recursive Processing**: Recursively applies chunking to each half.
4. **Result Combination**: Merges results from both halves, maintaining proper position offsets.

```python
# Recursive splitting in _recursive_chunk()
success, split_pos, error_msg = self._find_split_point(text, depth=depth, part=part_description)
left_text = text[:split_pos]
right_text = text[split_pos:]
# Recursively process each half...
```

### 4. Split Point Determination

The system uses a specialized prompt to find optimal semantic split points:

1. **Two-Step Prompt**: Asks the model to first explain its strategy, then provide the exact split point text between markers.
2. **Marker Extraction**: Uses regex to extract the exact split point text.
3. **Position Finding**: Locates this text in the document to determine the split position.
4. **Flexible Matching**: Falls back to flexible whitespace matching if needed.
5. **Conversation Tracking**: Records all interactions for debugging and analysis.

```python
# Marker-based extraction in _find_split_point()
split_pattern = re.compile(r'BEGIN_SPLIT_POINT\s*(.*?)\s*END_SPLIT_POINT', re.DOTALL)
match = split_pattern.search(full_response)
if match:
    response = match.group(1).strip()
```

## Validation and Error Handling

### Chunk Validation

The system performs comprehensive validation across multiple dimensions:

1. **JSON Parsing**: Ensures the LLM response contains valid JSON.
2. **Schema Validation**: Verifies the JSON conforms to the expected chunk schema.
3. **Extraction Validation**: Confirms all chunk markers can be found in the document.
4. **Size Validation**: Checks that chunks meet size constraints (max/min token counts).
5. **Coverage Validation**: Ensures no content is left out between chunks.

### Error Handling & Retry

When validation fails, the system:

1. Collects all errors (extraction, size, coverage) into a comprehensive report.
2. Provides specific, actionable feedback to the LLM.
3. Retries with this feedback for up to `max_retries` attempts.
4. Falls back to SimpleChunker if enabled and all retries fail.

```python
# Error collection and categorization
extraction_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "extraction_failed"])
size_exceeded_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "size_exceeded"])
size_too_small_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "size_too_small"])
coverage_errors = "\n".join([e["message"] for e in all_errors if e["type"] == "coverage_incomplete"])
```

## Configuration Parameters

### Initialization Parameters

- **ai_client**: The AI client to use (defaults to creating a new one)
- **prompt_template**: Custom prompt template (defaults to loading from file)
- **model_name**: Model to use (defaults to "gemini2.0flash")
- **max_retries**: Maximum retry attempts (default: 5)
- **fallback**: Whether to use SimpleChunker if LLM chunking fails
- **max_direct_tokens**: Threshold for direct vs. recursive chunking

### Chunking Parameters

- **max_chunk_size**: Maximum token count per chunk
- **overlap**: Token overlap between chunks (primarily for SimpleChunker)

## Debugging and Analysis

The system maintains detailed records for debugging:

1. **Conversation History**: Records all interactions for chunking.
2. **Split Conversations**: Tracks all document splitting operations.
3. **Metadata**: Records token counts, positions, and other details.
4. **Debug Output**: Can be saved to JSON for analysis.

## Implementation Notes

### Performance Optimizations

1. **Single-Chunk Shortcut**: Skips LLM calls for documents smaller than max_chunk_size.
2. **Targeted Retries**: Provides specific feedback to help the LLM correct errors.
3. **Flexible Matching**: Uses regex with whitespace flexibility for more robust marker matching.

### Error Recovery

1. **Progressive Refinement**: Each retry includes detailed error information.
2. **Fallback Mechanisms**: Multiple levels of fallbacks from exact to flexible matching.
3. **Graceful Degradation**: Can fall back to simpler chunking when needed.

### Safety Features

1. **Size Constraints**: Enforces both maximum and minimum chunk sizes.
2. **Coverage Validation**: Ensures no content is accidentally omitted.
3. **Position Tracking**: Maintains accurate position information through recursive operations.

## Usage Example

```python
from ai.chunking.strategies import LLMChunker
from ai.client import AI

# Create an AI client
ai_client = AI(model_name="gemini2.0flash")

# Create the chunker
chunker = LLMChunker(
    ai_client=ai_client,
    max_retries=3,
    fallback=True,
    max_direct_tokens=2000
)

# Process a document
with open("document.txt", "r") as f:
    text = f.read()

chunks = chunker.chunk(
    text=text,
    max_chunk_size=1000  # Target token count per chunk
)

# Use the resulting chunks
for chunk in chunks:
    print(f"Chunk {chunk.id}: {len(chunk.content)} chars, "
          f"{chunk.metadata['token_estimate']} tokens")
```

This technical implementation delivers semantically coherent document chunking that works reliably across documents of any size and complexity. 