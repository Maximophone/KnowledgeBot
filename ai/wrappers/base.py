from typing import List, Optional
from ..types import Message
from ..tools import Tool, ToolCall
from dataclasses import dataclass

@dataclass
class AIResponse:
    content: str
    tool_calls: Optional[List[ToolCall]] = None

class AIWrapper:
    def messages(self, model_name: str, messages: List[Message], 
                 system_prompt: str, max_tokens: int, 
                 temperature: float, tools: Optional[List[Tool]] = None) -> AIResponse:
        response = self._messages(model_name, messages, system_prompt, max_tokens, 
                                temperature, tools)
        return response
    
    def _messages(self, model: str, messages: List[Message], 
                 system_prompt: str, max_tokens: int, 
                 temperature: float, tools: Optional[List[Tool]] = None) -> AIResponse:
        raise NotImplementedError 