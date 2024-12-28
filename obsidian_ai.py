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
import ai
from ai import encode_image, validate_image
from typing import List, Dict, Tuple, Callable, Optional
import yaml
import anthropic
import os
import glob
import traceback
from file_watcher import start_file_watcher
from file_packager import get_committed_files, format_for_llm
from beacons import beacon_ai, beacon_error, beacon_me, beacon_tool
from parser.tag_parser import process_tags
from config import secrets
from ai.tools import test_get_weather, ToolCall, ToolResult

# Constants
DEFAULT_LLM = "sonnet3.5"
VAULT_PATH = "G:\\My Drive\\Obsidian"
VAULT_EXCLUDE = ["KnowledgeBot\\Meetings", "AI Chats", "MarkDownload", "gdoc", ".smart-connections"]
PROMPT_MOD = "You will be passed a document and some instructions to modify this document. Please reply strictly with the text of the new document (no surrounding xml, no narration).\n"

SEARCH_PATHS = [
    VAULT_PATH,
    "C:\\Users\\fourn\\code",
    # Add any other paths you want to search
]

# Initialize AI model
api_key = secrets.CLAUDE_API_KEY
client = anthropic.Client(api_key=api_key)
model = ai.AI("claude-haiku")

def remove_frontmatter(contents: str) -> str:
    return contents.split("---")[2]

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

def resolve_file_path(fname: str, subfolder: str = "") -> Optional[str]:
    """
    Resolve a file path based on various input formats.
    
    Args:
        fname (str): Filename or path
        subfolder (str): Subfolder to search within each search path
    
    Returns:
        Optional[str]: Resolved file path or None if not found
    """
    if fname.startswith("[[") and fname.endswith("]]"):
        fname = fname[2:-2].split("|")[0]
        return resolve_vault_fname(fname)
    
    potential_names = [fname, f"{fname}.md"]
    
    for base_path in SEARCH_PATHS:
        for name in potential_names:
            full_path = os.path.join(base_path, subfolder, name)
            if os.path.isfile(full_path):
                return full_path
    
    return None

def get_file_contents(fpath: str) -> str:
    """
    Read the contents of a file.
    
    Args:
        fpath (str): Path to the file
    
    Returns:
        str: File contents or error message
    """
    if fpath.endswith(".pdf"):
        return ai.extract_text_from_pdf(fpath)
    
    try:
        with open(fpath, "rb") as f:
            return f.read().decode('utf-8', errors='replace')
    except Exception as e:
        return f"Error reading file {fpath}: {str(e)}"

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
        contents = remove_frontmatter(contents)
        return contents
    
    return f"<{typ}><filename>{file_name}</filename>\n<contents>{contents}</contents></{typ}>"
# Define replacement functions
remove = lambda *_: ""
REPLACEMENTS_OUTSIDE = {
    "help": lambda *_: "This is the help\n",
    "ai": lambda value, text, context: process_ai_block(text, context, value),
}

REPLACEMENTS_INSIDE = {
    "reply": remove,
    "back": remove,
    "model": remove,
    "system": remove,
    "debug": remove,
    "temperature": remove,
    "max_tokens": remove,
    "mock": remove,
    "this": lambda v, t, context: f"<document>{context}</document>\n",
    "repo": pack_repo,
    "vault": lambda *_: pack_vault(),
    "meeting": lambda v, t, c: insert_file_ref(v, "KnowledgeBot\\Meetings\\Transcriptions"),
    "transcription": lambda v, t, c: insert_file_ref(v, "KnowledgeBot\\Transcriptions"),
    "daily": lambda v, t, c: insert_file_ref(v, "Daily Notes"),
    "idea": lambda v, t, c: insert_file_ref(v, "KnowledgeBot\\Ideas\\Transcriptions"),
    "unsorted": lambda v, t, c: insert_file_ref(v, "KnowledgeBot\\Unsorted\\Transcriptions"),
    "doc": lambda v, t, c: insert_file_ref(v),
    "pdf": lambda v, t, c: insert_file_ref(v, "pdf", typ="pdf"),
    "md": lambda v, t, c: insert_file_ref(v, "MarkDownload"),
    "file": lambda v, t, c: insert_file_ref(v),
    "prompt": lambda v, t, c: insert_file_ref(v, "Prompts", "prompt")
}

def get_markdown_files(directory: str) -> List[str]:
    """
    Get all markdown files in a directory and its subdirectories.

    Args:
        directory (str): Directory to search

    Returns:
        List[str]: List of markdown file paths
    """
    search_pattern = os.path.join(directory, '**', '*.md')
    return glob.glob(search_pattern, recursive=True)

def find_matching_path(file_list: List[str], end_path: str) -> str:
    """
    Find a matching file path from a list of paths. If multiple paths 
    match, the shortest one is returned

    Args:
        file_list (List[str]): List of file paths
        end_path (str): End of the path to match

    Returns:
        str: Matching file path or None
    """
    normalized_end = os.path.normpath(end_path)
    candidates = []
    for full_path in file_list:
        normalized_full = os.path.normpath(full_path)
        if normalized_full.endswith(normalized_end):
            candidates.append(full_path)
    if len(candidates) == 0:
        return None
    # We pick the shortest path out of the candidates
    return min(candidates, key=lambda x: len(x))

def resolve_vault_fname(fname: str, vault_path: str = VAULT_PATH) -> str:
    """
    Resolve a vault filename to its full path.

    Args:
        fname (str): Filename to resolve
        vault_path (str): Path to the vault

    Returns:
        str: Full path to the file or None if not found
    """
    fpaths_set = get_markdown_files(vault_path)
    fpath = find_matching_path(fpaths_set, fname+".md")
    return fpath

def escape_response(response: str) -> str:
    """
    Escape special keywords in the AI's response.

    Args:
        response (str): AI's response

    Returns:
        str: Escaped response
    """
    def create_replacement_func(key):
        def func(v, t, c):
            mod_key = key.upper()
            v = v or ""
            if t is None:
                return f"<{mod_key}!{v}>"
            else:
                return f"<{mod_key}!{v}>{t}</{mod_key}!>"
        return func
    
    replacements = {}
    names = list(REPLACEMENTS_OUTSIDE.keys()) + list(REPLACEMENTS_INSIDE.keys())
    for k in names:
        replacements[k] = create_replacement_func(k)
    new_response, _ = process_tags(response, replacements)
    return new_response

def process_file(file_path: str):
    """
    Process a modified file in the Obsidian vault.

    Args:
        file_path (str): Path to the modified file
    """
    try:
        print(f"File {file_path} modified", flush=True)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        doc_no_ai, _ = process_tags(content, {"ai": lambda *_: ""}) 
        context = {"doc": doc_no_ai, "new_doc": None}
        content, params = process_tags(content, REPLACEMENTS_OUTSIDE, context=context)

        if context["new_doc"]:
            content = context["new_doc"]

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        os.utime(file_path, None)

    except Exception:
        print(f"Error processing file {file_path}:")
        print(traceback.format_exc())

def process_ai_block(block: str, context: Dict, option: str) -> str:
    """
    Process an AI block in the document.

    Args:
        block (str): Content of the AI block
        context (Dict): Context information
        option (str): Processing option

    Returns:
        str: Processed AI block
    """
    option_txt = option or ""
    _, results = process_tags(block)
    if "reply" not in set([n for n,v,t in results]):
        return f"<ai!{option_txt}>{block}</ai!>"
    
    block, results = process_tags(block, {"reply": remove})
    try:
        # THERE CAN ONLY BE ONE >_<
        n_replies = [int(v) for n,v,t in results if n=="reply"][0]
    except TypeError:
        n_replies = 1

    try:
        conv_txt = block.strip()
        conv_txt, results = process_tags(conv_txt, REPLACEMENTS_INSIDE, context=context["doc"])
        params = dict([(n, v) for n, v, t in results])

        model_name = params.get("model", DEFAULT_LLM)
        system_prompt = params.get("system")
        debug = ("debug" in params)
        temperature = float(params.get("temperature", ai.DEFAULT_TEMPERATURE))
        max_tokens = int(params.get("max_tokens", ai.DEFAULT_MAX_TOKENS))
        if "mock" in params:
            model_name = "mock"

        if debug:
            print("---PARAMETERS START---", flush=True)
            for name, value in params.items():
                print(f"{name}: {value}", flush=True)
            print("---PARAMETERS END---", flush=True)
            print("---CONVERTED TEXT START---", flush=True)
            print(conv_txt.encode("utf-8"), flush=True)
            print("---CONVERTED TEXT END---", flush=True)

        print(f"Answering with {model_name}...", flush=True)
        if option != "all":
            messages = process_conversation(conv_txt)
        else:
            messages = process_conversation(f"{PROMPT_MOD}<document>{context['doc']}</document><instructions>{conv_txt}</instructions>")

        if system_prompt is not None:
            with open(f"prompts/{system_prompt}.md", "r") as f:
                system_prompt = f.read()

        response = ""
        for i in range(n_replies):
            if n_replies > 1:
                response += f"==[VERSION-{i}]==\n"
            
            # Get available tools from the parameters
            tools = [test_get_weather]  # TODO: Get tools from parameters/config
            
            ai_response = model.messages(messages, model_override=model_name,
                                    max_tokens=max_tokens, temperature=temperature,
                                    tools=tools)
            response += ai_response.content

            # Handle tool calls if present
            if ai_response.tool_calls:
                for tool_call in ai_response.tool_calls:
                    try:
                        # Find the matching tool from provided tools
                        tool = next(t for t in tools if t.tool.name == tool_call.name)
                        # Execute the tool
                        result = tool.tool.func(**tool_call.arguments)
                        # Format the result
                        tool_result = ToolResult(
                            name=tool_call.name,
                            result=result,
                            tool_call_id=tool_call.id
                        )
                    except Exception as e:
                        tool_result = ToolResult(
                            name=tool_call.name,
                            result=None,
                            tool_call_id=tool_call.id,
                            error=str(e)
                        )
                    
                    # Add tool result to response for UI
                    response += f"\n{beacon_tool}\n"
                    response += f"Tool: {tool_result.name}\n"
                    if tool_result.error:
                        response += f"Error: {tool_result.error}\n"
                    else:
                        response += f"Result: {tool_result.result}\n"
                    
                    # Add tool result to messages for context
                    messages.append({
                        "role": "assistant",
                        "content": response
                    })
                    messages.append({
                        "role": "tool",  # New role type for tool results
                        "tool_call_id": tool_result.tool_call_id,
                        "name": tool_result.name,
                        "content": tool_result  # Pass the entire ToolResult object
                    })
                    
                    # Get AI's response to tool result
                    ai_response = model.messages(messages, model_override=model_name,
                                            max_tokens=max_tokens, temperature=temperature,
                                            tools=tools)  # Keep passing tools
                    response += f"\n{beacon_ai}\n{ai_response.content}\n"

        response = escape_response(response)
        if option is None:
            new_block = f"{block}{beacon_ai}\n{response}\n{beacon_me}\n"
        elif option == "rep":
            return response
        elif option == "all":
            context["new_doc"] = response
            return response
    except Exception:
        new_block = f"{block}{beacon_error}\n```sh\n{traceback.format_exc()}```\n"
    return f"<ai!{option_txt}>{new_block}</ai!>"

def process_conversation(txt: str) -> List[Dict[str, str]]:
    cut = [t.split(beacon_me) for t in txt.split(beacon_ai)]
    # [[<claude>, <me>], [<claude>, <me>], ... ]
    assert len(cut[0]) == 1 or len(cut[0]) == 2
    assert all(len(x)==2 for x in cut[1:])
    if len(cut[0]) == 1:
        cut[0] = ["", cut[0][0]]
    assert cut[0][0] == ""

    def process_user_message(message: str) -> Dict[str, str]:
        processed, results = process_tags(message, {"image": remove })
        image_paths = [v for n, v, _ in results if n == "image"]
        if image_paths:
            content = []
            for image_path in image_paths:
                try:
                    validate_image(image_path)
                    encoded_image, media_type = encode_image(image_path)
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded_image
                        }
                    })
                except (FileNotFoundError, ValueError) as e:
                    print(f"Error processing image {image_path}: {str(e)}")
            content.append({"type": "text", "text": processed.strip()})
            return {"role": "user", "content": content}
        else:
            return {"role": "user", "content": processed.strip()}

    messages = sum([[
        {"role": "assistant", "content": cl.strip()},
        process_user_message(me)
    ] for cl, me in cut], [])[1:]
    
    assert messages[0]["role"] == "user"
    assert messages[-1]["role"] == "user"
    return messages


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
        if rep == "ai":
            continue
        if rep in all_tags:
            return True
    if "ai" not in all_tags:
        return False
    ai_results = [r for r in results if r[0] == "ai"]
    for name, value, txt in ai_results:
        if txt is None:
            continue
        _, results = process_tags(txt)
        if "reply" in set(n for n,v,t in results):
            return True
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Obsidian AI Assistant')
    args = parser.parse_args()

    start_file_watcher(VAULT_PATH, process_file, needs_answer, use_polling=True)