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

# Add parent directory to path to allow importing from the chunking module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ai.chunking import Chunker, LLMChunker, SimpleChunker
from ai.chunking.utils import load_text_file, display_chunks, save_chunks_to_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        # The LLMChunker will initialize its own AI client
        return LLMChunker(
            model_name=model_name,
            max_retries=max_retries,
            fallback=fallback
        )
    except Exception as e:
        logger.error(f"Failed to create LLMChunker: {str(e)}")
        if fallback:
            logger.info("Falling back to SimpleChunker")
            return SimpleChunker()
        else:
            raise


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
    text = load_text_file(file_path)
    logger.info(f"Document loaded: {len(text)} characters")
    
    logger.info(f"Chunking document with {chunker.__class__.__name__}")
    chunks = Chunker(chunker).chunk(
        text, 
        max_chunk_size=max_chunk_size, 
        overlap=overlap
    )
    
    logger.info(f"Created {len(chunks)} chunks")
    return chunks


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
    parser.add_argument("--retries", "-r", type=int, default=3,
                        help="Maximum retry attempts")
    parser.add_argument("--no-fallback", action="store_true",
                        help="Disable fallback to SimpleChunker if LLM chunking fails")
    parser.add_argument("--output", help="Output file to save chunks (optional)")
    parser.add_argument("--format", choices=["json", "text"], default="json",
                        help="Output format for saving chunks")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    parser.add_argument("--compare", "-c", action="store_true",
                        help="Compare with SimpleChunker results")
    
    args = parser.parse_args()
    
    try:
        # Create LLM chunker
        llm_chunker = create_llm_chunker(
            model_name=args.model,
            max_retries=args.retries,
            fallback=not args.no_fallback,
            verbose=args.verbose
        )
        
        # Chunk the document
        chunks = chunk_document(
            file_path=args.file,
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
                file_path=args.file,
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
        
        return 0
    
    except Exception as e:
        logger.error(f"Error during chunking: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 