from typing import List, Tuple
from obsidian.beacons import beacon_me, beacon_ai, beacon_tool_start, beacon_tool_end, beacon_tokens_prefix
from obsidian.parser.tag_parser import process_tags
import json
from ai_core.types import Message, MessageContent, ToolCall, ToolResult
from ai_core.image_utils import validate_image, encode_image
import re
import logging

remove = lambda *_: ""

logger = logging.getLogger(__name__)

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
    # Remove chain-of-thought blocks so they don't get parsed into messages
    txt = re.sub(r'\|THOUGHT\|.*?\|/THOUGHT\|', '', txt, flags=re.DOTALL)

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
                ai_response = parts[0]
                
                # Remove token beacons if present
                if beacon_tokens_prefix in ai_response:
                    # Find and remove the token beacon
                    token_start = ai_response.find(beacon_tokens_prefix)
                    if token_start != -1:
                        token_end = ai_response.find("|==", token_start)
                        if token_end != -1:
                            # Remove the entire token beacon including newline
                            token_beacon = ai_response[token_start:token_end + 3]
                            if token_beacon.endswith("\n"):
                                token_end += 1
                            ai_response = ai_response[:token_start] + ai_response[token_end + 3:]
                
                text_parts = ai_response.split(beacon_tool_start)
                
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
    if messages[0].role != "user":
        logger.error(f"Conversation must start with user message, but got {messages[0].role}")
        logger.debug(f"Conversation: {txt}")
        raise ValueError("Conversation must start with user message")
    if messages[-1].role != "user":
        # Create a summary of all messages for better error reporting
        message_summary = []
        for i, msg in enumerate(messages):
            content_preview = ""
            if hasattr(msg, 'content') and msg.content:
                if isinstance(msg.content, list):
                    # Handle list of MessageContent objects
                    text_parts = []
                    for content_item in msg.content:
                        if hasattr(content_item, 'text') and content_item.text:
                            text_parts.append(content_item.text)
                    content_preview = " ".join(text_parts)
                elif isinstance(msg.content, str):
                    content_preview = msg.content
                else:
                    content_preview = str(msg.content)
            
            # Truncate to first 100 characters
            content_preview = content_preview[:100] + "..." if len(content_preview) > 100 else content_preview
            message_summary.append(f"Message {i}: {msg.role} - {content_preview}")
        
        error_msg = f"Conversation must end with user message, but got {messages[-1].role}. Messages:\n" + "\n".join(message_summary)
        logger.error(error_msg)
        logger.debug(f"Conversation: {txt}")
        raise ValueError(error_msg)
    return messages


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