from integrations.html_to_markdown import HTMLToMarkdown
from ai.file_packager import get_committed_files, format_for_llm
from obsidian.beacons import beacon_me, beacon_ai, beacon_error
from obsidian.file_utils import resolve_file_path, get_file_contents, get_markdown_files, remove_frontmatter, VAULT_PATH
import os

VAULT_EXCLUDE = ["KnowledgeBot\\Meetings", "AI Chats", "MarkDownload", "gdoc", ".smart-connections"]

# Initialize HTML to Markdown converter
html_to_md = HTMLToMarkdown()

def pack_repo(path: str) -> str:
    """
    Package the repository files for AI context.

    Args:
        path (str): Path to the repository

    Returns:
        str: Formatted repository content
    """
    packaged = get_committed_files(path)
    packaged_txt = format_for_llm(packaged)
    packaged_txt = packaged_txt.replace(beacon_me, "|ME|").replace(beacon_ai, "|AI|").replace(beacon_error, "|ERROR|")
    return f"<repository>{packaged_txt}</repository>\n"

def pack_vault() -> str:
    """
    Package the Obsidian vault files for AI context.

    Returns:
        str: Formatted vault content
    """
    packaged = get_markdown_files(VAULT_PATH, VAULT_EXCLUDE)
    packaged_txt = format_for_llm(packaged)
    return f"<vault>{packaged_txt}</vault>\n"

def insert_file_ref(fname: str = "", subfolder: str = "", typ: str = "document") -> str:
    """
    Insert a reference to a file in the AI context.
    
    Args:
        fname (str): Filename
        subfolder (str): Subfolder to search within each search path
        typ (str): Type of document
    
    Returns:
        str: Formatted file reference
    """
    resolved_path = resolve_file_path(fname, subfolder)
    
    if not resolved_path:
        return f"Error: Cannot find file {fname}"
    
    file_name = os.path.basename(resolved_path)
    contents = get_file_contents(resolved_path)

    if typ=="prompt":
        # we remove the frontmatter, and insert the prompt as is
        try:
            contents = remove_frontmatter(contents)
        except IndexError:
            contents = contents
        return contents
    
    return f"<{typ}><filename>{file_name}</filename>\n<contents>{contents}</contents></{typ}>"


def fetch_url_content(url: str) -> str:
    """
    Fetch and convert URL content to markdown.
    
    Args:
        url (str): URL to fetch
        
    Returns:
        str: Markdown content
    """
    try:
        return html_to_md.convert_url(url)
    except Exception as e:
        return f"Error fetching URL: {str(e)}"