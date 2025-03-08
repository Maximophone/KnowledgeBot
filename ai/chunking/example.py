#!/usr/bin/env python3
"""
Example usage of the chunking module.
"""

import sys
import os
import argparse

# Add parent directory to path to allow importing from the chunking module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ai.chunking import Chunker, SimpleChunker, LLMChunker
from ai.chunking.utils import load_text_file, display_chunks, save_chunks_to_file


def main():
    """
    Main function to demonstrate chunking functionality.
    """
    parser = argparse.ArgumentParser(description="Document chunking example")
    parser.add_argument("--file", "-f", help="Path to text file to chunk", required=True)
    parser.add_argument("--strategy", "-s", choices=["simple", "llm"], default="simple",
                      help="Chunking strategy to use")
    parser.add_argument("--size", "-z", type=int, default=1000,
                      help="Maximum chunk size (characters for simple, tokens for LLM)")
    parser.add_argument("--overlap", "-o", type=int, default=0,
                      help="Overlap between chunks")
    parser.add_argument("--output", help="Output file to save chunks (optional)")
    parser.add_argument("--format", choices=["json", "text"], default="json",
                      help="Output format for saving chunks")
    
    args = parser.parse_args()
    
    # Load file
    try:
        text = load_text_file(args.file)
        print(f"Loaded {args.file}: {len(text)} characters")
    except Exception as e:
        print(f"Error loading file: {e}")
        return 1
    
    # Create chunker with selected strategy
    if args.strategy == "simple":
        chunker = Chunker(SimpleChunker())
        print(f"Using simple chunking strategy with max_chunk_size={args.size}, overlap={args.overlap}")
    else:  # args.strategy == "llm"
        chunker = Chunker(LLMChunker())
        print(f"Using LLM chunking strategy with max_chunk_size={args.size}, overlap={args.overlap}")
        print("Note: LLM chunking is not fully implemented and will use simple chunking as a fallback")
    
    # Perform chunking
    chunks = chunker.chunk(text, max_chunk_size=args.size, overlap=args.overlap)
    
    # Display results
    print(f"\nCreated {len(chunks)} chunks:")
    display_chunks(chunks)
    
    # Save chunks if output file specified
    if args.output:
        save_chunks_to_file(chunks, args.output, args.format)
        print(f"Saved chunks to {args.output} in {args.format} format")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 