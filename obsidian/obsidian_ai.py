"""
obsidian_ai.py

This module serves as the entry point for the Obsidian AI Assistant. It provides functionality
to process Obsidian markdown files, interact with AI models, and manage file operations within
an Obsidian vault.

The assistant can:
- Watch for changes in Obsidian vault files
- Process custom tags in markdown files
- Interact with AI models to generate responses
- Modify files based on AI responses and user-defined rules

Key components:
- Custom tag parsing (using parser.tag_parser)
- AI model interaction (using ai module)
- File watching and processing
- Vault and repository packaging for context

Author: [Your Name]
Date: [Current Date]
"""

import argparse
import os
import traceback
from services.file_watcher import start_file_watcher
from obsidian.parser.tag_parser import process_tags
from config.logging_config import setup_logger
from obsidian.file_utils import VAULT_PATH
from obsidian.process_ai_block import REPLACEMENTS_OUTSIDE

logger = setup_logger(__name__)

def process_file(file_path: str):
    """
    Process a modified file in the Obsidian vault.

    Args:
        file_path (str): Path to the modified file
    """
    logger.info("File %s modified", file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        doc_no_ai, _ = process_tags(content, {"ai": lambda *_: ""}) 
        context = {"doc": doc_no_ai, "new_doc": None, "file_path": file_path}
        content, params = process_tags(content, REPLACEMENTS_OUTSIDE, context=context)

        if context["new_doc"]:
            content = context["new_doc"]

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        os.utime(file_path, None)

    except Exception:
        logger.error("Error processing file %s:", file_path)
        logger.error(traceback.format_exc())


def needs_answer(file_path: str) -> bool:
    """
    Check if a file needs an AI answer.

    Args:
        file_path (str): Path to the file

    Returns:
        bool: True if the file needs an answer, False otherwise
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    _, results = process_tags(content)
    all_tags = set([name for name, _, _ in results])
    for rep in REPLACEMENTS_OUTSIDE.keys():
        if rep == "ai" or rep == "rag":
            continue
        if rep in all_tags:
            return True
    
    # Check for AI blocks that need responses
    if "ai" in all_tags:
        ai_results = [r for r in results if r[0] == "ai"]
        for name, value, txt in ai_results:
            if txt is None:
                continue
            _, inner_results = process_tags(txt)
            if "reply" in set(n for n,v,t in inner_results):
                return True
    
    # Check for RAG blocks that need responses
    if "rag" in all_tags:
        rag_results = [r for r in results if r[0] == "rag"]
        for name, value, txt in rag_results:
            if txt is None:
                continue
            _, inner_results = process_tags(txt)
            if "reply" in set(n for n,v,t in inner_results):
                return True
    
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Obsidian AI Assistant')
    args = parser.parse_args()

    start_file_watcher(VAULT_PATH, process_file, needs_answer, use_polling=True)