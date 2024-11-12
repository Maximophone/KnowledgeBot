import yaml
from typing import Dict, Any, Optional

def parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
    """
    Extract and parse YAML frontmatter from markdown content.
    
    Args:
        content: String containing markdown content with potential frontmatter
        
    Returns:
        Dictionary of frontmatter data or None if no frontmatter found
    """
    if not content.startswith('---\n'):
        return None
        
    try:
        # Find the end of frontmatter
        _, remaining = content.split('---\n', 1)
        if '\n---\n' not in remaining:
            return None
            
        fm_content, _ = remaining.split('\n---\n', 1)
        return yaml.safe_load(fm_content)
        
    except (yaml.YAMLError, ValueError):
        return None

def frontmatter_to_text(frontmatter: Dict[str, Any]) -> str:
    """
    Convert a frontmatter dictionary to YAML text format.
    
    Args:
        frontmatter: Dictionary of frontmatter data
        
    Returns:
        Formatted string with YAML frontmatter delimiters
    """
    yaml_text = yaml.dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False
    )
    return f"---\n{yaml_text}---\n"

def update_frontmatter(content: str, updates: Dict[str, Any]) -> str:
    """
    Update existing frontmatter in markdown content.
    
    Args:
        content: Original markdown content with frontmatter
        updates: Dictionary of frontmatter fields to update
        
    Returns:
        Updated content string
    """
    existing = parse_frontmatter(content)
    if existing is None:
        existing = {}
        
    existing.update(updates)
    
    if content.startswith('---\n'):
        # Remove existing frontmatter
        parts = content.split('---\n', 2)
        if len(parts) >= 3:
            content = parts[2]
        else:
            content = parts[-1]
            
    return frontmatter_to_text(existing) + content