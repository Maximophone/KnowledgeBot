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
from ai.image_utils import encode_image, validate_image
from typing import List, Dict, Tuple, Callable, Optional, Any
import yaml
import anthropic
import os
import glob
import traceback
from services.file_watcher import start_file_watcher
from ai.file_packager import get_committed_files, format_for_llm
from obsidian.beacons import beacon_ai, beacon_error, beacon_me, beacon_tool_start, beacon_tool_end
from obsidian.parser.tag_parser import process_tags
from config import secrets
from ai.tools import Tool, ToolCall, ToolResult
from ai.toolsets import TOOL_SETS
from ai.types import Message, MessageContent
from config.paths import PATHS
from integrations.html_to_markdown import HTMLToMarkdown
from config.logging_config import setup_logger
from ui.tool_confirmation import confirm_tool_execution
import json

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

# Initialize HTML to Markdown converter
html_to_md = HTMLToMarkdown()

logger = setup_logger(__name__)

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
        try:
            contents = remove_frontmatter(contents)
        except IndexError:
            contents = contents
        return contents
    
    return f"<{typ}><filename>{file_name}</filename>\n<contents>{contents}</contents></{typ}>"

def get_tools_from_key(key: str) -> List[Tool]:
    """Get tools from a predefined key"""
    return TOOL_SETS.get(key, [])

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
    "tools": remove,
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
    "prompt": lambda v, t, c: insert_file_ref(v, "Prompts", "prompt"),
    "url": lambda v, t, c: f"<url>{v}</url>\n<content>{fetch_url_content(v)}</content>\n",
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

def process_ai_block(block: str, context: Dict, option: str) -> str:
    """
    Process an AI block in the document.

    Args:
        block (str): Content of the AI block
        context (Dict): Context information including file_path
        option (str): Processing option (None, "rep", or "all")

    Returns:
        str: Processed AI block
    """
    option_txt = option or ""
    _, results = process_tags(block)
    if "reply" not in set([n for n,v,t in results]):
        return f"<ai!{option_txt}>{block}</ai!>"
    initial_block = block
    block, results = process_tags(block, {"reply": remove})

    try:
        # Add immediate feedback that AI is processing
        current_content = update_file_content(
            initial_block,
            f"{beacon_ai}\n_Thinking..._\n",
            context["file_path"]
        )

        conv_txt = block.strip()
        conv_txt, results = process_tags(conv_txt, REPLACEMENTS_INSIDE, context=context["doc"])
        params = dict([(n, v) for n, v, t in results])

        model_name = params.get("model", DEFAULT_LLM)
        system_prompt = params.get("system")
        debug = ("debug" in params)
        temperature = float(params.get("temperature", ai.DEFAULT_TEMPERATURE))
        max_tokens = int(params.get("max_tokens", ai.DEFAULT_MAX_TOKENS))
        tools_keys = [v for n, v, t in results if n == "tools" and v]
        tools = merge_tools(tools_keys)
        if "mock" in params:
            model_name = "mock"

        if debug:
            logger.debug("---PARAMETERS START---")
            for name, value in params.items():
                logger.debug("%s: %s", name, value)
            logger.debug("---PARAMETERS END---")
            logger.debug("---CONVERTED TEXT START---")
            logger.debug("%s", conv_txt.encode("utf-8"))
            logger.debug("---CONVERTED TEXT END---")

        logger.info("Answering with %s...", model_name)
        if option != "all":
            messages = process_conversation(conv_txt)
        else:
            messages = process_conversation(f"{PROMPT_MOD}<document>{context['doc']}</document><instructions>{conv_txt}</instructions>")

        if system_prompt is not None:
            # Search through multiple paths for the system prompt
            prompt_found = False
            for prompts_path in ["./prompts", PATHS.prompts_library]:
                prompt_path = os.path.join(prompts_path, f"{system_prompt}.md")
                if os.path.exists(prompt_path):
                    with open(prompt_path, "r", encoding="utf-8") as f:
                        system_prompt = f.read()
                        prompt_found = True
                        break
            
            if not prompt_found:
                raise FileNotFoundError(f"Could not find system prompt '{system_prompt}' in any search paths")
        
        ai_response = model.messages(messages, system_prompt=system_prompt, model_override=model_name,
                                    max_tokens=max_tokens, temperature=temperature,
                                    tools=tools)
        response = ""
        
        start = True
        while True:  # Process responses until no more tool calls
            response += ai_response.content

            if ai_response.content.strip():
                escaped_response = escape_response(ai_response.content)
                current_content = update_file_content(
                    current_content,
                    f"{beacon_ai if start else ''}\n{escaped_response}\n",
                    context["file_path"]
                )
                start = False

            if not ai_response.tool_calls:
                break  # No (more) tool calls, we're done

            # Process all tool calls at once
            tool_results = []
            for tool_call in ai_response.tool_calls:
                tool_call_text = format_tool_call(tool_call)
                current_content = update_file_content(
                    current_content,
                    tool_call_text,
                    context["file_path"]
                )
                try:
                    # Find the matching tool from provided tools
                    tool = next(t for t in tools if t.tool.name == tool_call.name)
                    
                    # Check if tool needs confirmation
                    if not tool.tool.safe:
                        if not confirm_tool_execution(tool.tool, tool_call.arguments):
                            # User rejected the tool execution
                            tool_result = ToolResult(
                                name=tool_call.name,
                                result=None,
                                tool_call_id=tool_call.id,
                                error="Tool execution rejected by user"
                            )
                            tool_results.append(tool_result)
                            tool_result_text = format_tool_result(tool_result)
                            current_content = update_file_content(
                                current_content,
                                tool_result_text,
                                context["file_path"]
                            )
                            continue
                    
                    # Execute the tool
                    result = tool.tool.func(**tool_call.arguments)
                    # Format the result
                    tool_result = ToolResult(
                        name=tool_call.name,
                        result=result,
                        tool_call_id=tool_call.id
                    )
                    tool_results.append(tool_result)
                    tool_result_text = format_tool_result(tool_result)
                    current_content = update_file_content(
                        current_content,
                        tool_result_text,
                        context["file_path"]
                    )
                except Exception as e:
                    tool_result = ToolResult(
                        name=tool_call.name,
                        result=None,
                        tool_call_id=tool_call.id,
                        error=f"{str(e)}\n{traceback.format_exc()}"
                    )
                    tool_results.append(tool_result)
                    tool_result_text = format_tool_result(tool_result)
                    current_content = update_file_content(
                        current_content,
                        tool_result_text,
                        context["file_path"]
                    )
            
            # Add tool calls and results to response text
            for tool_call, tool_result in zip(ai_response.tool_calls, tool_results):
                response += "\n" + format_tool_call(tool_call)
                response += format_tool_result(tool_result)
            
            # Add tool call and result to messages for context
            assistant_content = []
            if ai_response.content.strip():  # Only add text content if non-empty
                assistant_content.append(MessageContent(
                    type="text",
                    text=ai_response.content
                ))
            # Add tool calls
            assistant_content.extend([
                MessageContent(
                    type="tool_use",
                    tool_call=tool_call
                ) for tool_call in ai_response.tool_calls
            ])
            
            messages.append(Message(
                role="assistant",
                content=assistant_content
            ))

            # Add all tool results in a single user message
            messages.append(Message(
                role="user",
                content=[MessageContent(
                    type="tool_result",
                    tool_result=result
                ) for result in tool_results]
            ))
            
            # Get AI's response to tool results
            ai_response = model.messages(messages, system_prompt=system_prompt, model_override=model_name,
                                    max_tokens=max_tokens, temperature=temperature,
                                    tools=tools)

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

def format_tool_call(tool_call: ToolCall) -> str:
    """Format a tool call into a parseable string"""
    return (
        f"{beacon_tool_start}\n"
        f"ID: {tool_call.id}\n"
        f"Tool: {tool_call.name}\n"
        f"Arguments:\n"
        f"```json\n"
        f"{json.dumps(tool_call.arguments, indent=2)}\n"
        f"```\n"
    )

def format_tool_result(result: ToolResult) -> str:
    """Format a tool result into a parseable string"""
    return (
        f"Result:\n"
        f"```json\n"
        f"{json.dumps({'result': result.result, 'error': result.error}, indent=2)}\n"
        f"```\n"
        f"{beacon_tool_end}\n"
    )

def parse_tool_section(section: str) -> Tuple[ToolCall, ToolResult]:
    """Parse a tool section back into ToolCall and ToolResult objects"""
    lines = section.strip().split('\n')
    tool_id = lines[1].split(': ')[1]
    tool_name = lines[2].split(': ')[1]
    
    # Find where arguments end and result starts
    arg_start = lines.index('Arguments:') + 2
    result_start = lines.index('Result:') + 2
    
    # Parse arguments and result
    arguments = json.loads('\n'.join(lines[arg_start:result_start-3]))  # Skip the end of the block quote
    results = json.loads('\n'.join(lines[result_start:-2])) # Skip the last line because it contains the closing tag
    
    tool_call = ToolCall(
        id=tool_id,
        name=tool_name,
        arguments=arguments
    )
    
    tool_result = ToolResult(
        name=tool_name,
        tool_call_id=tool_id,
        result=results['result'],
        error=results['error']
    )
    
    return tool_call, tool_result

def process_conversation(txt: str) -> List[Message]:
    """
    Process a conversation text into a list of structured messages for the AI.
    
    This function handles the complex task of converting a text-based conversation
    (with beacons and tool interactions) into a structured format that can be sent
    to the AI. The conversation text is expected to alternate between AI and user
    messages, separated by beacons (beacon_ai and beacon_me).

    The process works as follows:
    1. Split the text into sections using AI beacons
    2. For each section, split again using ME beacons
    3. Process each part maintaining the conversation structure:
        - First section must start with empty text before ME beacon
        - AI responses may contain tool calls enclosed in TOOL_START/TOOL_END tags
        - Tool calls and their results are parsed and reconstructed into proper objects
        - Images in user messages are processed and encoded

    Structure of the input text:
    ```
    <initial user message>
    |AI|
    <ai response>
    [possibly including tool calls:
    |TOOL_START|
    ID: <tool_id>
    Tool: <tool_name>
    Arguments: <json_args>
    Result: {
        'value': <result>,
        'error': <error>
    }
    |TOOL_END|]
    |ME|
    <user response>
    |AI|
    ...and so on
    ```

    Args:
        txt (str): The conversation text to process

    Returns:
        List[Message]: A list of Message objects representing the conversation.
        Each Message contains:
        - role: "user" or "assistant"
        - content: List[MessageContent] where each content can be:
            * text: Regular message text
            * tool_use: A tool call from the AI
            * tool_result: Result of a tool execution
            * image: An encoded image

    Requirements:
        - Conversation must start with a user message
        - Conversation must end with a user message
        - Tool calls must maintain their order and pairing with results
        - All tool sections must be properly formatted

    Example:
        Input text:
        ```
        What's the weather?
        |AI|
        Let me check...
        |TOOL_START|
        ID: call_123
        Tool: get_weather
        Arguments: {"city": "Paris"}
        Result: {'value': "22°C", 'error': null}
        |TOOL_END|
        It's 22°C in Paris
        |ME|
        Thanks!
        ```

        Results in messages:
        [
            Message(role="user", content=[MessageContent(type="text", text="What's the weather?")]),
            Message(role="assistant", content=[
                MessageContent(type="text", text="Let me check..."),
                MessageContent(type="tool_use", tool_call=ToolCall(...))
            ]),
            Message(role="user", content=[MessageContent(type="tool_result", tool_result=ToolResult(...))]),
            Message(role="user", content=[MessageContent(type="text", text="Thanks!")])
        ]
    """
    cut = [t.split(beacon_me) for t in txt.split(beacon_ai)]
    if len(cut[0]) == 1:
        cut[0] = ["", cut[0][0]]
    assert cut[0][0] == ""

    def process_user_message(message: str) -> Message:
        processed, results = process_tags(message, {"image": remove })
        image_paths = [v for n, v, _ in results if n == "image"]
        content = []
        if image_paths:
            for image_path in image_paths:
                try:
                    validate_image(image_path)
                    encoded_image, media_type = encode_image(image_path)
                    content.append(MessageContent(
                        type="image",
                        text=None,
                        tool_call=None,
                        tool_result=None,
                        image={
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded_image
                        }
                    ))
                except (FileNotFoundError, ValueError) as e:
                    print(f"Error processing image {image_path}: {str(e)}")
        content.append(MessageContent(
            type="text",
            text=processed.strip()
        ))
        return Message(role="user", content=content)

    messages = []
    for i, parts in enumerate(cut):
        if i == 0:
            if parts[1].strip():  # Only add if there's content
                messages.append(process_user_message(parts[1]))
        else:
            if parts[0].strip():
                # Process AI response including any tool calls
                content = []
                text_parts = parts[0].split(beacon_tool_start)
                
                # Add initial text if present
                if text_parts[0].strip():
                    content.append(MessageContent(
                        type="text",
                        text=text_parts[0].strip()
                    ))
                
                # Process tool sections
                tool_sections = []
                for section in text_parts[1:]:
                    section = beacon_tool_start + section
                    if beacon_tool_end in section:
                        tool_section = section[:section.index(beacon_tool_end) + len(beacon_tool_end)]
                        tool_call, tool_result = parse_tool_section(tool_section)
                        content.append(MessageContent(
                            type="tool_use",
                            tool_call=tool_call
                        ))
                        tool_sections.append((tool_call, tool_result))
                
                messages.append(Message(role="assistant", content=content))
                
                # Add tool results as a separate user message
                if tool_sections:
                    messages.append(Message(
                        role="user",
                        content=[MessageContent(
                            type="tool_result",
                            tool_result=result
                        ) for _, result in tool_sections]
                    ))
            
            if len(parts) > 1 and parts[1].strip():
                messages.append(process_user_message(parts[1]))
    
    # Ensure conversation starts with user and ends with user
    assert messages[0].role == "user"
    assert messages[-1].role == "user"
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

def merge_tools(tools_keys: List[str]) -> List[Tool]:
    """Merge multiple toolsets together"""
    all_tools = []
    for key in tools_keys:
        tools = get_tools_from_key(key)
        if tools:
            all_tools.extend(tools)
    return all_tools

def update_file_content(current_content: str, new_text: str, file_path: str) -> str:
    """
    Update the file by finding the current content and appending new text to it.
    
    Args:
        current_content (str): Current content to find in the file
        new_text (str): New text to append
        file_path (str): Path to the file to update
    
    Returns:
        str: Updated current_content
    """
    # Update current content with new text
    updated_content = f"{current_content}{new_text}"
    
    # Read the full file
    with open(file_path, "r", encoding="utf-8") as f:
        full_content = f.read()
    
    # Replace the exact current content with updated content
    full_content = full_content.replace(current_content, updated_content)
    
    # Write the updated content back to file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    os.utime(file_path, None) # necessary to trigger Obsidian to reload the file

    return updated_content

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Obsidian AI Assistant')
    args = parser.parse_args()

    start_file_watcher(VAULT_PATH, process_file, needs_answer, use_polling=True)