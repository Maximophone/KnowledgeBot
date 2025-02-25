from ai import AI, DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from ai.types import Message, MessageContent, ToolCall, ToolResult
from typing import Dict, List
from obsidian.beacons import beacon_me, beacon_ai, beacon_error
from obsidian.process_conversation import process_conversation
import os
from obsidian.parser.tag_parser import process_tags
from ui.tool_confirmation import confirm_tool_execution
from config.paths import PATHS
from integrations.twitter_api import TwitterAPI
import json
import traceback
from config.logging_config import setup_logger
from obsidian.beacons import beacon_tool_start, beacon_tool_end
from ai.toolsets import TOOL_SETS
from ai.tools import Tool
from ai.models import DEFAULT_MODEL
from obsidian.context_pulling import pack_repo, pack_vault, insert_file_ref, fetch_url_content

logger = setup_logger(__name__)

# Constants
PROMPT_MOD = "You will be passed a document and some instructions to modify this document. Please reply strictly with the text of the new document (no surrounding xml, no narration).\n"

# New constants
beacon_thought = "|THOUGHT|"
beacon_end_thought = "|/THOUGHT|"

# Initialize AI model
model = AI("claude-haiku")
twitter_api = TwitterAPI()

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
    "tweet": lambda v, t, c: twitter_api.thread_to_markdown(v) or f"Error: Could not fetch tweet from {v}",
}

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

        model_name = params.get("model", DEFAULT_MODEL)
        system_prompt = params.get("system")
        debug = ("debug" in params)
        temperature = float(params.get("temperature", DEFAULT_TEMPERATURE))
        max_tokens = int(params.get("max_tokens", DEFAULT_MAX_TOKENS))
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
        thoughts = ""
        
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
                if ai_response.reasoning and ai_response.reasoning.strip():
                    logger.debug("Reasoning: %s", ai_response.reasoning[:100])
                    escaped_reasoning = escape_response(ai_response.reasoning)
                    thought_block = f"\n{beacon_thought}\n{escaped_reasoning}\n{beacon_end_thought}\n"
                    thoughts += thought_block
                    current_content = update_file_content(current_content, thought_block, context["file_path"])

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
                        confirmed, user_message = confirm_tool_execution(tool.tool, tool_call.arguments)
                        if not confirmed:
                            # User rejected the tool execution
                            error_msg = "Tool execution rejected by user"
                            if user_message:
                                error_msg += f"\nUser message: {user_message}"
                            tool_result = ToolResult(
                                name=tool_call.name,
                                result=None,
                                tool_call_id=tool_call.id,
                                error=error_msg
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
            new_block = f"{block}{beacon_ai}\n{thoughts}\n{response}\n{beacon_me}\n"
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

def get_tools_from_key(key: str) -> List[Tool]:
    """Get tools from a predefined key"""
    return TOOL_SETS.get(key, [])

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