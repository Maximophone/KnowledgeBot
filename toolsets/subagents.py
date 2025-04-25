from ai_core.tools import tool, Tool, ToolCall, ToolResult
from ai_core.client import AI
from ai_core.types import Message, MessageContent
import json
import traceback
from typing import List, Optional, Dict, Tuple
from uuid import uuid4
from .obsidian import read_obsidian_note

# Store active conversations
_conversations: Dict[str, AI] = {}

def _handle_tool_calls(agent: AI, response: Message, tools: List[Tool]) -> Tuple[str, List[ToolCall], List[ToolResult]]:
    """Helper function to handle tool calls and create response loop"""
    final_response = response.content
    all_tool_calls = []
    all_tool_results = []
    
    while response.tool_calls:
        tool_results = []
        
        # Create assistant message with tool calls
        messages = [Message(
            role="assistant",
            content=[
                MessageContent(type="text", text=response.content),
                *[MessageContent(type="tool_use", tool_call=tc) for tc in response.tool_calls]
            ]
        )]
        
        # Process each tool call
        for tool_call in response.tool_calls:
            all_tool_calls.append(tool_call)
            try:
                # Find the matching tool
                tool = next((t for t in tools if t.tool.name == tool_call.name), None)
                if not tool:
                    raise ValueError(f"Tool {tool_call.name} not found")
                
                # Skip unsafe tools
                if not tool.tool.safe:
                    tool_result = ToolResult(
                        name=tool_call.name,
                        result=None,
                        tool_call_id=tool_call.id,
                        error="Unsafe tools are not allowed for subagents"
                    )
                else:
                    # Execute the tool
                    result = tool.tool.func(**tool_call.arguments)
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
                    error=f"{str(e)}\n{traceback.format_exc()}"
                )
            
            tool_results.append(tool_result)
            all_tool_results.append(tool_result)
        
        # Add tool results to messages
        messages.append(Message(
            role="user",
            content=[MessageContent(
                type="tool_result",
                tool_result=result
            ) for result in tool_results]
        ))
        
        # Get AI's response to tool results
        response = agent.messages(messages)
        if response.content:
            final_response += "\n" + response.content
    
    return final_response, all_tool_calls, all_tool_results

@tool(
    description="Create a new AI subagent with specified configuration. This tool allows spawning a new AI instance "
                "with custom model, system prompt, and tools. The subagent can then be used for specific subtasks "
                "or specialized processing.\n\n"
                "Note Path Handling:\n"
                "- When note paths are provided, their contents will be prepended to the system prompt in a special\n"
                "  'OBSIDIAN CONTEXT BLOCK' formatted as:\n"
                "  <!-- Begin referenced notes -->\n"
                "  <note path='...'>...</note>\n"
                "  <!-- End referenced notes -->\n"
                "- The subagent should reference these notes using their full path when citing sources\n\n"
                "Available Models:\n"
                "- haiku3.5: Fast and cost-effective, but with reduced performance. Best for simple tasks.\n"
                "- sonnet3.7: Well-balanced performance and cost. Good all-around choice for most tasks.\n"
                "- deepseek-reasoner: Specialized in complex reasoning and problem-solving tasks.\n\n"
                "Available Toolsets:\n"
                "- memory: Tools for storing and retrieving information persistently\n"
                "- gmail: Email operations (send, search, read)\n"
                "- linkedin: Professional network interactions\n"
                "- obsidian: Note-taking and knowledge management\n"
                "- system: Basic system operations\n"
                "- subagents: Create and manage other AI agents (note: nested subagents should be used carefully)\n\n"
                "Choose the model based on the task complexity - use cheaper models for simple tasks and more powerful ones for complex reasoning.",
    model_identifier="The model to use for the subagent (e.g., 'haiku3.5', 'sonnet3.5', 'deepseek-reasoner')",
    system_prompt="The system prompt that defines the subagent's behavior and capabilities",
    toolset_names="Optional comma-separated list of toolset names to give the subagent access to (e.g., 'memory,gmail')",
    note_paths="Optional comma-separated list of Obsidian note paths to include as formatted context. Notes will be "
                "prepended to the system prompt in an XML-like block with their full vault path and content. "
                "Example: 'Projects/AI.md, Meetings/Q2.md'",
    safe=True
)
def spawn_subagent(
    model_identifier: str,
    system_prompt: str,
    toolset_names: str = "",
    note_paths: str = ""
) -> str:
    """Creates a new AI subagent with the specified configuration"""
    from . import TOOL_SETS

    # Parse and validate note paths
    note_context = []
    note_errors = []
    
    if note_paths:
        for path in note_paths.split(','):
            path = path.strip()
            content = read_obsidian_note(path)
            if content.startswith("Error:"):
                note_errors.append(f"Failed to read note '{path}': {content}")
            else:
                note_context.append(f"<note path='{path}'>\n{content}\n</note>")
    
    # If any notes failed to load, return error
    if note_errors:
        return json.dumps({
            "error": "Failed to load one or more notes:\n" + "\n".join(note_errors)
        })
    
    # Only add context block if we have notes
    if note_context:
        system_prompt = (
            f"OBSIDIAN CONTEXT BLOCK:\n"
            f"<!-- Begin referenced notes -->\n"
            f"{''.join(note_context)}\n"
            f"<!-- End referenced notes -->\n\n"
            f"{system_prompt}"
        )

    # Parse comma-separated toolset names
    toolset_list = [name.strip() for name in toolset_names.split(",") if name.strip()]
    
    # Get tools from TOOL_SETS
    tools = []
    for toolset_name in toolset_list:
        if toolset_name in TOOL_SETS:
            tools.extend(TOOL_SETS[toolset_name])

    # Create new AI instance
    agent = AI(
        model_identifier=model_identifier,
        system_prompt=system_prompt,
        tools=tools
    )
    
    # Generate unique ID for this agent
    agent_id = str(uuid4())
    _conversations[agent_id] = agent
    
    return json.dumps({
        "agent_id": agent_id,
        "model": model_identifier,
        "tools": [t.tool.name for t in tools]  # Access name directly from Tool object
    })

@tool(
    description="Send a one-time prompt to a subagent and get its response. This is useful for quick, one-off "
                "interactions where you don't need to maintain conversation history. The subagent must have been "
                "created first using spawn_subagent.",
    agent_id="The ID of the subagent to interact with (obtained from spawn_subagent)",
    prompt="The message/prompt to send to the subagent",
    safe=True
)
def prompt_subagent(agent_id: str, prompt: str) -> str:
    """Sends a one-time prompt to a subagent"""
    if agent_id not in _conversations:
        return json.dumps({"error": "Agent not found"})
    
    agent = _conversations[agent_id]
    response = agent.message(prompt)
    
    # Handle tool calls and get final response
    final_response, tool_calls, tool_results = _handle_tool_calls(agent, response, agent.tools)
    
    return json.dumps({
        "response": final_response,
        "tool_calls": [
            {
                "name": tc.name,
                "arguments": tc.arguments,
                "result": next((tr.result for tr in tool_results if tr.tool_call_id == tc.id), None),
                "error": next((tr.error for tr in tool_results if tr.tool_call_id == tc.id), None)
            } for tc in tool_calls
        ]
    })

@tool(
    description="Start a new conversation with a subagent that maintains history. This creates a new conversation "
                "context where the subagent will remember previous interactions. Returns a conversation ID that can "
                "be used with continue_conversation.",
    agent_id="The ID of the subagent to start a conversation with",
    initial_message="The first message to send to the subagent",
    safe=True
)
def start_conversation(agent_id: str, initial_message: str) -> str:
    """Starts a new conversation with a subagent"""
    if agent_id not in _conversations:
        return json.dumps({"error": "Agent not found"})
    
    agent = _conversations[agent_id]
    response = agent.conversation(initial_message)
    
    # Handle tool calls and get final response
    final_response, tool_calls, tool_results = _handle_tool_calls(agent, response, agent.tools)
    
    return json.dumps({
        "response": final_response,
        "tool_calls": [
            {
                "name": tc.name,
                "arguments": tc.arguments,
                "result": next((tr.result for tr in tool_results if tr.tool_call_id == tc.id), None),
                "error": next((tr.error for tr in tool_results if tr.tool_call_id == tc.id), None)
            } for tc in tool_calls
        ]
    })

@tool(
    description="Continue an existing conversation with a subagent. This allows sending follow-up messages in a "
                "conversation where the subagent maintains context of previous interactions.",
    agent_id="The ID of the subagent to continue conversing with",
    message="The next message in the conversation",
    safe=True
)
def continue_conversation(agent_id: str, message: str) -> str:
    """Continues an existing conversation with a subagent"""
    if agent_id not in _conversations:
        return json.dumps({"error": "Agent not found"})
    
    agent = _conversations[agent_id]
    response = agent.conversation(message)
    
    # Handle tool calls and get final response
    final_response, tool_calls, tool_results = _handle_tool_calls(agent, response, agent.tools)
    
    return json.dumps({
        "response": final_response,
        "tool_calls": [
            {
                "name": tc.name,
                "arguments": tc.arguments,
                "result": next((tr.result for tr in tool_results if tr.tool_call_id == tc.id), None),
                "error": next((tr.error for tr in tool_results if tr.tool_call_id == tc.id), None)
            } for tc in tool_calls
        ]
    })

@tool(
    description="List all active subagent conversations. This shows information about all spawned subagents "
                "including their IDs, models, and available tools.",
    safe=True
)
def list_conversations() -> str:
    """Lists all active subagent conversations"""
    return json.dumps({
        agent_id: {
            "model": agent.model_identifier,
            "tools": [t.tool.name for t in agent.tools]
        }
        for agent_id, agent in _conversations.items()
    })

# Export the tools
TOOLS = [
    spawn_subagent,
    prompt_subagent,
    start_conversation,
    continue_conversation,
    list_conversations
] 