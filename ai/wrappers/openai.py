from openai import OpenAI
from typing import List, Optional
from .base import AIWrapper, AIResponse
from ..types import Message, MessageContent
from ..tools import Tool, ToolCall
import json
import logging

logger = logging.getLogger(__name__)

class GPTWrapper(AIWrapper):
    def __init__(self, api_key: str, org: str):
        self.client = OpenAI(api_key=api_key)#, organization=org)

    def _messages(self, model_name: str, messages: List[Message], 
                 system_prompt: str, max_tokens: int, temperature: float,
                 tools: Optional[List[Tool]] = None,
                 thinking: bool = False, thinking_budget_tokens: Optional[int] = None) -> AIResponse:
        if system_prompt:
            messages = [Message(role="system", content=[MessageContent(type="text", text=system_prompt)])] + messages
            
        # Convert tools to OpenAI's format if provided
        openai_tools = None
        if tools:
            openai_tools = [{
                "type": "function",
                "function": {
                    "name": tool.tool.name,
                    "description": tool.tool.description,
                    "parameters": {
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
                        ],
                        "additionalProperties": False
                    }
                }
            } for tool in tools]

        # Convert messages to OpenAI's format
        openai_messages = []
        for message in messages:
            if message.role == "tool":
                tool_result = next(content.tool_result for content in message.content if content.type == "tool_result")
                openai_messages.append({
                    "role": "tool",
                    "content": json.dumps({
                        "result": tool_result.result,
                        "error": tool_result.error
                    }),
                    "tool_call_id": tool_result.tool_call_id
                })
            else:
                content_list = []
                for msg_content in message.content:
                    if msg_content.type == "text":
                        content_list.append({
                            "type": "text",
                            "text": msg_content.text
                        })
                    elif msg_content.type == "image":
                        content_list.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{msg_content.image['media_type']};base64,{msg_content.image['data']}"
                            }
                        })
                openai_messages.append({
                    "role": message.role,
                    "content": content_list[0]["text"] if len(content_list) == 1 and content_list[0]["type"] == "text" else content_list
                })

        if model_name.startswith("o1") or model_name.startswith("o3") or model_name.startswith("o4"):
            response = self.client.chat.completions.create(
                model=model_name,
                messages=openai_messages,
                max_completion_tokens=max_tokens,
                tools=openai_tools
            )
        else:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=openai_tools
            )
        
        # Extract reasoning content if available
        logger.debug(response.choices[0])
        reasoning = getattr(response.choices[0].message, "reasoning_content", None)
        # Check if the model wants to use a tool
        if response.choices[0].message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=json.loads(tool_call.function.arguments)
                )
                for tool_call in response.choices[0].message.tool_calls
            ]
            return AIResponse(
                content=response.choices[0].message.content or "",
                tool_calls=tool_calls,
                reasoning=reasoning
            )
        return AIResponse(
            content=response.choices[0].message.content,
            reasoning=reasoning
        ) 