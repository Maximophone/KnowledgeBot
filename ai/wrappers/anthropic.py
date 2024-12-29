import anthropic
from typing import List, Optional
from .base import AIWrapper, AIResponse
from ..types import Message
from ..tools import Tool, ToolCall

class ClaudeWrapper(AIWrapper):
    def __init__(self, api_key: str):
        self.client = anthropic.Client(api_key=api_key)

    def _messages(self, model: str, messages: List[Message], 
                 system_prompt: str, max_tokens: int, temperature: float,
                 tools: Optional[List[Tool]] = None) -> AIResponse:
        # Convert tools to Claude's format if provided
        claude_tools = None
        if tools:
            claude_tools = [{
                "name": tool.tool.name,
                "description": tool.tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        name: {
                            "type": param.type,
                            "description": param.description,
                            **({"enum": param.enum} if param.enum else {})
                        }
                        for name, param in tool.tool.parameters.items()
                    },
                    "required": [
                        name for name, param in tool.tool.parameters.items()
                        if param.required
                    ]
                }
            } for tool in tools]

        # Convert messages to Claude's format
        claude_messages = []
        for message in messages:
            claude_content = []
            for content in message.content:
                if content.type == "text":
                    claude_content.append({"type": "text", "text": content.text})
                elif content.type == "tool_use":
                    claude_content.append({
                        "type": "tool_use",
                        "id": content.tool_call.id,
                        "name": content.tool_call.name,
                        "input": content.tool_call.arguments
                    })
                elif content.type == "tool_result":
                    claude_content.append({
                        "type": "tool_result",
                        "tool_use_id": content.tool_result.tool_call_id,
                        "content": str(content.tool_result.result) if content.tool_result.result is not None 
                                 else f"Error: {content.tool_result.error}"
                    })
                elif content.type == "image":
                    claude_content.append({
                        "type": "image",
                        "source": {
                            "type": content.image["type"],
                            "media_type": content.image["media_type"],
                            "data": content.image["data"]
                        }
                    })
            
            claude_messages.append({
                "role": message.role,
                "content": claude_content
            })

        arguments = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": claude_messages
        }
        if claude_tools:
            arguments["tools"] = claude_tools

        response = self.client.messages.create(**arguments)

        # Extract content and any tool calls
        content = ""
        tool_calls = []
        
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input
                ))

        return AIResponse(
            content=content,
            tool_calls=tool_calls if tool_calls else None
        ) 