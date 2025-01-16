import yaml
from typing import Dict, Any, Optional
from config.logging_config import setup_logger
from pathlib import Path

logger = setup_logger(__name__)

def read_front_matter(file_path):
    front_matter = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        # Check for the start of front matter
        line = f.readline()
        if line.strip() != '---':
            return front_matter  # No front matter present
        # Read lines until the end of front matter
        yaml_lines = []
        for line in f:
            if line.strip() == '---':
                break  # End of front matter
            yaml_lines.append(line)
        # Parse the YAML content
        yaml_content = ''.join(yaml_lines)
        try:
            front_matter = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.error("Error parsing YAML front matter in %s: %s", file_path, e)
            front_matter = {}
    return front_matter

def update_front_matter(file_path, new_front_matter):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # Check if the file has front matter
    if lines[0].strip() != '---':
        # No front matter, so add it
        front_matter_str = '---\n' + yaml.dump(new_front_matter) + '---\n'
        new_content = front_matter_str + ''.join(lines)
    else:
        # Replace existing front matter
        end_index = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == '---':
                end_index = i
                break
        if end_index is None:
            print(f"Error: Closing '---' not found in {file_path}")
            return
        front_matter_str = '---\n' + yaml.dump(new_front_matter) + '---\n'
        new_content = front_matter_str + ''.join(lines[end_index+1:])
    # Write the updated content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

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