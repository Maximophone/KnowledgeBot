#!/usr/bin/env python3
"""
Example demonstrating LLM-based document chunking.
This example shows how to use the LLMChunker strategy
with the retry mechanism for handling LLM response errors.
"""

import sys
import os
import argparse
import logging
import json
import traceback
from datetime import datetime

# Configure logging first before imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path to allow importing from the chunking module
try:
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logger.info(f"Adding parent directory to path: {parent_dir}")
    sys.path.append(parent_dir)
except Exception as e:
    logger.error(f"Error setting up path: {e}")
    traceback.print_exc()
    sys.exit(1)

# Now import modules
try:
    from ai.chunking import Chunker, LLMChunker, SimpleChunker
    from ai.chunking.utils import load_text_file, display_chunks, save_chunks_to_file
    logger.info("Successfully imported chunking modules")
except Exception as e:
    logger.error(f"Error importing modules: {e}")
    traceback.print_exc()
    sys.exit(1)


def create_llm_chunker(model_name, max_retries, fallback, verbose):
    """
    Create an LLMChunker with specified parameters.
    
    Args:
        model_name: The model to use for chunking
        max_retries: Maximum retry attempts
        fallback: Whether to fall back to SimpleChunker if LLM chunking fails
        verbose: Enable verbose logging
        
    Returns:
        LLMChunker instance
    """
    logger.info(f"Creating LLMChunker with model={model_name}, max_retries={max_retries}, fallback={fallback}")
    
    if verbose:
        # Set logging level for all loggers
        for handler in logging.root.handlers:
            handler.setLevel(logging.DEBUG)
        # Also set for specific modules
        logging.getLogger('ai.chunking').setLevel(logging.DEBUG)
        logging.getLogger('ai.chunking.strategies').setLevel(logging.DEBUG)
        logging.getLogger('ai.chunking.llm_parser').setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Create the LLMChunker - no fallback, as requested
    chunker = LLMChunker(
        model_name=model_name,
        max_retries=max_retries,
        fallback=fallback
    )
    logger.info(f"LLMChunker created successfully")
    return chunker


def chunk_document(file_path, chunker, max_chunk_size, overlap):
    """
    Chunk a document using the provided chunker.
    
    Args:
        file_path: Path to the document file
        chunker: The chunking strategy to use
        max_chunk_size: Maximum chunk size
        overlap: Overlap between chunks
        
    Returns:
        List of chunks
    """
    logger.info(f"Loading document from {file_path}")
    
    # Check if file exists
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")
        
    # Load the file
    text = load_text_file(file_path)
    logger.info(f"Document loaded: {len(text)} characters")
    logger.debug(f"Document preview: {text[:100]}...")
    
    logger.info(f"Chunking document with {chunker.__class__.__name__}")
    chunks = Chunker(chunker).chunk(
        text, 
        max_chunk_size=max_chunk_size, 
        overlap=overlap
    )
    
    logger.info(f"Created {len(chunks)} chunks")
    return chunks


def save_debug_info(base_filename, llm_chunker, chunks=None, error=None):
    """
    Save debug information including conversation history and chunks to a file.
    
    Args:
        base_filename: Base filename to use for the debug file
        llm_chunker: LLMChunker instance with conversation history
        chunks: List of generated chunks (can be None if chunking failed)
        error: Error information if chunking failed
        
    Returns:
        Path to the debug file
    """
    # Generate debug filename based on base_filename
    if not base_filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_filename = f"chunker_debug_{timestamp}.txt"
    else:
        # Use the same directory as the base_filename but with _debug suffix
        dirname = os.path.dirname(base_filename)
        basename = os.path.basename(base_filename)
        name, ext = os.path.splitext(basename)
        debug_filename = os.path.join(dirname, f"{name}_debug.txt")
    
    logger.info(f"Saving debug information to {debug_filename}")
    
    with open(debug_filename, "w", encoding="utf-8") as f:
        # Write header
        f.write(f"=== CHUNKER DEBUG INFO ===\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Model: {llm_chunker.model_name}\n")
        if error:
            f.write(f"Status: FAILED - {error}\n")
        else:
            f.write(f"Status: SUCCESS\n")
        f.write("\n")
        
        # Write system prompt
        f.write("=== SYSTEM PROMPT ===\n")
        token_value = "Use your judgment" if not hasattr(llm_chunker, '_last_max_chunk_size') else llm_chunker._last_max_chunk_size
        try:
            system_prompt = llm_chunker.prompt_template.format(max_token_count=token_value)
            f.write(system_prompt)
        except Exception as e:
            f.write(f"Error formatting system prompt: {str(e)}\n")
            f.write(f"Raw prompt template:\n{llm_chunker.prompt_template}\n")
        f.write("\n\n")
        
        # Write conversation history
        f.write("=== CONVERSATION HISTORY ===\n")
        if hasattr(llm_chunker, 'conversation_history') and llm_chunker.conversation_history:
            for i, message in enumerate(llm_chunker.conversation_history):
                f.write(f"--- Message {i+1} ({message.role}) ---\n")
                for content in message.content:
                    if content.type == "text":
                        f.write(content.text)
                    else:
                        f.write(f"[Content type: {content.type}]")
                f.write("\n\n")
        else:
            f.write("No conversation history available.\n\n")
        
        # Write error information if available
        if error:
            f.write("=== ERROR INFORMATION ===\n")
            f.write(f"{error}\n\n")
        
        # Write final chunks
        f.write("=== FINAL CHUNKS ===\n")
        if chunks and len(chunks) > 0:
            f.write(f"Total chunks: {len(chunks)}\n\n")
            
            for i, chunk in enumerate(chunks):
                f.write(f"--- Chunk {i+1} ---\n")
                f.write(f"ID: {chunk.id}\n")
                f.write(f"Position: {chunk.start_pos} - {chunk.end_pos}\n")
                f.write(f"Size: {chunk.size} characters\n")
                f.write(f"Metadata: {json.dumps(chunk.metadata, indent=2)}\n")
                f.write(f"Content preview: {chunk.content[:100]}...\n")
                f.write("\n")
        else:
            f.write("No chunks generated due to error or empty result.\n")
    
    logger.info(f"Debug information saved to {debug_filename}")
    return debug_filename


def main():
    """Main function to demonstrate LLM chunking."""
    parser = argparse.ArgumentParser(description="LLM-based document chunking example")
    parser.add_argument("--file", "-f", help="Path to text file to chunk", required=True)
    parser.add_argument("--model", "-m", default="gemini2.0flash", 
                        help="Model to use for LLM chunking")
    parser.add_argument("--size", "-s", type=int, default=1000,
                        help="Maximum chunk size (tokens)")
    parser.add_argument("--overlap", "-o", type=int, default=0,
                        help="Overlap between chunks")
    parser.add_argument("--retries", "-r", type=int, default=5,
                        help="Maximum retry attempts")
    parser.add_argument("--fallback", action="store_true",
                        help="Enable fallback to SimpleChunker if LLM chunking fails")
    parser.add_argument("--output", help="Output file to save chunks (optional)")
    parser.add_argument("--format", choices=["json", "text"], default="json",
                        help="Output format for saving chunks")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    parser.add_argument("--compare", "-c", action="store_true",
                        help="Compare with SimpleChunker results")
    parser.add_argument("--debug-env", action="store_true",
                        help="Print environment information for debugging")
    parser.add_argument("--save-debug", action="store_true",
                        help="Save debugging information about the chunking process")
    
    args = parser.parse_args()
    
    # Print environment information if requested
    if args.debug_env:
        logger.info("Environment information:")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {sys.platform}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.info(f"Script location: {os.path.abspath(__file__)}")
        try:
            import ai
            logger.info(f"AI module version: {getattr(ai, '__version__', 'unknown')}")
            logger.info(f"Available models: {getattr(ai, 'available_models', 'unknown')}")
        except (ImportError, AttributeError):
            logger.error("AI module information not available")
    
    llm_chunker = None
    chunks = None
    error_info = None
    
    try:
        # Normalize file path
        file_path = os.path.normpath(args.file)
        logger.info(f"Normalized file path: {file_path}")
        
        # Create LLM chunker
        llm_chunker = create_llm_chunker(
            model_name=args.model,
            max_retries=args.retries,
            fallback=args.fallback,
            verbose=args.verbose
        )
        
        # Store the max_chunk_size value for debugging
        llm_chunker._last_max_chunk_size = args.size
        
        # Chunk the document
        chunks = chunk_document(
            file_path=file_path,
            chunker=llm_chunker,
            max_chunk_size=args.size,
            overlap=args.overlap
        )
        
        # Display results
        print(f"\nCreated {len(chunks)} chunks:")
        display_chunks(chunks)
        
        # Compare with SimpleChunker if requested
        if args.compare:
            print("\nComparing with SimpleChunker:")
            simple_chunker = SimpleChunker()
            simple_chunks = chunk_document(
                file_path=file_path,
                chunker=simple_chunker,
                max_chunk_size=args.size,
                overlap=args.overlap
            )
            
            print(f"SimpleChunker created {len(simple_chunks)} chunks")
            print(f"LLMChunker created {len(chunks)} chunks")
            
            # Show token distribution
            llm_tokens = [c.metadata.get("token_estimate", 0) for c in chunks]
            simple_tokens = [c.metadata.get("token_estimate", 0) for c in simple_chunks]
            
            if llm_tokens:
                print(f"LLMChunker token distribution: min={min(llm_tokens)}, "
                      f"max={max(llm_tokens)}, avg={sum(llm_tokens)/len(llm_tokens):.1f}")
            
            if simple_tokens:
                print(f"SimpleChunker token distribution: min={min(simple_tokens)}, "
                      f"max={max(simple_tokens)}, avg={sum(simple_tokens)/len(simple_tokens):.1f}")
        
        # Save chunks if output file specified
        if args.output:
            save_chunks_to_file(chunks, args.output, args.format)
            print(f"Saved chunks to {args.output} in {args.format} format")
        
        return_code = 0
        
    except Exception as e:
        logger.error(f"Error during chunking: {str(e)}")
        traceback.print_exc()
        error_info = f"{str(e)}\n\n{traceback.format_exc()}"
        return_code = 1
    
    finally:
        # Save debug information if requested or if there was an error
        if (args.save_debug or args.verbose or error_info) and llm_chunker:
            try:
                debug_file = save_debug_info(
                    args.output, 
                    llm_chunker, 
                    chunks=chunks, 
                    error=error_info
                )
                print(f"Debug information saved to {debug_file}")
            except Exception as debug_e:
                logger.error(f"Error saving debug information: {str(debug_e)}")
        
        return return_code


if __name__ == "__main__":
    sys.exit(main()) 