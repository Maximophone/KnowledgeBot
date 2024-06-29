import re
from typing import List, Tuple, Optional, Dict, Callable, Any

def process_tags(content: str, replacements: Dict[str, Callable[[Optional[str], Optional[str], Any], str]] = {},
    context: Any = None) -> Tuple[str, List[Tuple[str, Optional[str], Optional[str]]]]:
    
    pattern = r'<(\w+)!(?:"((?:[^"\\]|\\.)*)"|\[\[(.*?)\]\]|([^>\s]+))?>(.*?)</\1!>|<(\w+)!(?:"((?:[^"\\]|\\.)*)"|\[\[(.*?)\]\]|([^>\s]+))?>'
    processed = []

    def callback(match):
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
                # Quoted value
                value = re.sub(r'\\(.)', r'\1', value[1:-1])
            elif match.group(3) or match.group(8):  # [[...]] format
                value = f"[[{value}]]"
            else:
                # Unquoted value
                value = value.replace('\\ ', ' ')
        else:
            value = None
        
        if name in replacements:
            result = replacements[name](value, text, context)
        else:
            result = match.group(0)
        
        processed.append((name, value, text))
        return result

    result = re.sub(pattern, callback, content, flags=re.DOTALL)
    return result, processed