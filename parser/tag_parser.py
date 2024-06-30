"""
tag_parser.py

This module provides functionality for parsing and processing custom tags in text content.
It is designed to handle various tag formats, including those used in Obsidian-style markdown.

The main function, process_tags, can parse tags with the following formats:
- <name!value>content</name!>
- <name!"quoted value">content</name!>
- <name![[value]]>content</name!>
- <name!>content</name!>
- <name!value>
- <name!"quoted value">
- <name![[value]]>
- <name!>

The function can also apply custom replacements to the parsed tags.

Author: [Your Name]
Date: [Current Date]
"""

import re
from typing import List, Tuple, Optional, Dict, Callable, Any

def process_tags(content: str, 
                 replacements: Dict[str, Callable[[Optional[str], Optional[str], Any], str]] = {},
                 context: Any = None) -> Tuple[str, List[Tuple[str, Optional[str], Optional[str]]]]:
    """
    Parse and process custom tags in the given content.

    This function identifies tags in the content, extracts their name, value, and inner text,
    and optionally applies replacements based on the provided replacements dictionary.

    Args:
        content (str): The input text containing tags to be processed.
        replacements (Dict[str, Callable]): A dictionary of tag names to replacement functions.
            Each function should take three arguments: value, text, and context.
        context (Any): Additional context to be passed to replacement functions.

    Returns:
        Tuple[str, List[Tuple[str, Optional[str], Optional[str]]]]: 
            - The processed content with any replacements applied.
            - A list of tuples, each containing (tag_name, tag_value, tag_text).

    Tag Formats:
        - <name!value>content</name!>
        - <name!"quoted value">content</name!>
        - <name![[value]]>content</name!>
        - <name!>content</name!>
        - <name!value>
        - <name!"quoted value">
        - <name![[value]]>
        - <name!>

    Note:
        - Quoted values can contain escaped quotes: \\"
        - [[...]] format is preserved as-is, including spaces within the brackets.
        - Spaces in unquoted values must be escaped with a backslash.
    """
    
    # Regex pattern to match all supported tag formats
    pattern = r'<(\w+)!(?:"((?:[^"\\]|\\.)*)"|\[\[(.*?)\]\]|([^>\s]+))?>(.*?)</\1!>|<(\w+)!(?:"((?:[^"\\]|\\.)*)"|\[\[(.*?)\]\]|([^>\s]+))?>'
    processed = []

    def callback(match):
        """
        Process each matched tag and apply replacements if necessary.

        This inner function is called for each regex match in the content.
        It extracts the tag components and applies any specified replacements.

        Args:
            match: A regex match object

        Returns:
            str: The processed tag, either replaced or as-is
        """
        if match.group(1):  # Matched a tag with content
            name = match.group(1)
            value = match.group(2) or match.group(3) or match.group(4)
            text = match.group(5)
        else:  # Matched a self-closing tag
            name = match.group(6)
            value = match.group(7) or match.group(8) or match.group(9)
            text = None
        
        # Handle different value formats
        if value:
            if value.startswith('"') and value.endswith('"'):
                # Quoted value: remove quotes and unescape
                value = re.sub(r'\\(.)', r'\1', value[1:-1])
            elif match.group(3) or match.group(8):  # [[...]] format
                # Preserve [[...]] format, including spaces
                value = f"[[{value}]]"
            else:
                # Unquoted value: replace escaped spaces
                value = value.replace('\\ ', ' ')
        else:
            value = None
        
        # Apply replacement if the tag name is in the replacements dictionary
        if name in replacements:
            result = replacements[name](value, text, context)
        else:
            result = match.group(0)  # Keep the original tag if no replacement
        
        processed.append((name, value, text))
        return result

    # Apply the regex and callback to the content
    result = re.sub(pattern, callback, content, flags=re.DOTALL)
    return result, processed