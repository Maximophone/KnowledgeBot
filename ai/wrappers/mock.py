from typing import List, Optional
from .base import AIWrapper, AIResponse
from ..types import Message
from ..tools import Tool

class MockWrapper(AIWrapper):
    def __init__(self):
        pass

    def _messages(self, model_name: str, messages: List[Message],
        system_prompt: str, max_tokens: int, temperature:float, tools: Optional[List[Tool]] = None) -> AIResponse:
        response = "---PARAMETERS START---\n"
        response += f"max_tokens: {max_tokens}\n"
        response += f"temperature: {temperature}\n"
        response += "---PARAMETERS END---\n"

        response += "---SYSTEM PROMPT START---\n"
        response += system_prompt + "\n"
        response += "---SYSTEM PROMPT END---\n"

        if tools:
            response += "---TOOLS START---\n"
            for tool in tools:
                tool = tool.tool
                response += f"Tool: {tool.name}\n"
                response += f"Description: {tool.description}\n"
                response += "Parameters:\n"
                for param_name, param in tool.parameters.items():
                    response += f"  - {param_name}:\n"
                    response += f"    type: {param.type}\n"
                    response += f"    description: {param.description}\n"
                    response += f"    required: {param.required}\n"
                    if param.enum:
                        response += f"    enum: {param.enum}\n"
                response += "\n"
            response += "---TOOLS END---\n"

        response += "---MESSAGES START---\n"
        for message in messages:
            response += f"role: {message.role}\n"
            response += "content: \n"
            for content in message.content:
                if content.type == "text":
                    response += content.text + "\n"
                elif content.type == "tool_use":
                    response += f"[tool_use: {content.tool_call}]\n"
                elif content.type == "tool_result":
                    response += f"[tool_result: {content.tool_result}]\n"
        response += "---MESSAGES END---\n"

        return AIResponse(content=response) 