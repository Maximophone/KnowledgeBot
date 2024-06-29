import re
from typing import List, Tuple, Optional, Dict, Callable, Any

def parse_tags(content: str) -> List[Tuple[str, Optional[str], Optional[str]]]:
    # Pattern for outermost tags with three types of values:
    # 1. No value
    # 2. Unquoted values without spaces
    # 3. Quoted values that can contain anything
    pattern = r'<(\w+)!(?:"((?:[^"\\]|\\.)*)"|((?:[^>\s]|\\ )*)?)?>(.*?)</\1!>|<(\w+)!(?:"((?:[^"\\]|\\.)*)"|((?:[^>\s]|\\ )*)?)?>'
    
    results = []
    
    for match in re.finditer(pattern, content, re.DOTALL):
        if match.group(1):  # Matched a tag with content
            name, value, text = match.group(1), match.group(2) or match.group(3), match.group(4)
        else:  # Matched a self-closing tag
            name, value, text = match.group(5), match.group(6) or match.group(7), None
        
        # Unescape any escaped characters in quoted values
        if value and (match.group(2) is not None or match.group(6) is not None):  # This means it was a quoted value
            value = re.sub(r'\\(.)', r'\1', value)
        elif value:  # Unquoted value
            value = value.replace('\\ ', ' ')  # Replace escaped spaces
        
        # If value is an empty string, set it to None
        value = value if value else None
        
        results.append((name, value, text))
    
    return results

def process_tags(content: str, replacements: Dict[str, Callable[[Optional[str], Optional[str], Any], str]] = {},
    context: Any = None) -> Tuple[str, List[Tuple[str, Optional[str], Optional[str]]]]:
    
    pattern = r'<(\w+)!(?:"((?:[^"\\]|\\.)*)"|((?:[^>\s]|\\ )*)?)?>(.*?)</\1!>|<(\w+)!(?:"((?:[^"\\]|\\.)*)"|((?:[^>\s]|\\ )*)?)?>'
    processed = []

    def callback(match):
        if match.group(1):  # Matched a tag with content
            name, value, text = match.group(1), match.group(2) or match.group(3), match.group(4)
        else:  # Matched a self-closing tag
            name, value, text = match.group(5), match.group(6) or match.group(7), None
        
        # Unescape quoted values
        if value and (match.group(2) is not None or match.group(6) is not None):
            value = re.sub(r'\\(.)', r'\1', value)
        elif value:
            value = value.replace('\\ ', ' ')
        
        value = value if value else None
        
        if name in replacements:
            result = replacements[name](value, text, context)
        else:
            result = match.group(0)
        
        processed.append((name, value, text))
        return result

    result = re.sub(pattern, callback, content, flags=re.DOTALL)
    return result, processed