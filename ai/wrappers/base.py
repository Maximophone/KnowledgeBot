from typing import List, Optional
from ..types import Message
from ..tools import Tool, ToolCall
from dataclasses import dataclass
from ..tokens import (
    count_tokens_input, count_tokens_output, 
    log_token_use
)

@dataclass
class AIResponse:
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    reasoning: Optional[str] = None

class AIWrapper:
    def messages(self, model_name: str, messages: List[Message], 
                 system_prompt: str, max_tokens: int, 
                 temperature: float, tools: Optional[List[Tool]] = None,
                 thinking: bool = False, thinking_budget_tokens: Optional[int] = None) -> AIResponse:
        response = self._messages(model_name, messages, system_prompt, max_tokens, 
                                temperature, tools, thinking, thinking_budget_tokens)
        log_token_use(model_name, count_tokens_input(messages, system_prompt))
        log_token_use(model_name, count_tokens_output(response.content), input=False)
        return response
        
    def _messages(self, model: str, messages: List[Message], 
                 system_prompt: str, max_tokens: int, 
                 temperature: float, tools: Optional[List[Tool]] = None,
                 thinking: bool = False, thinking_budget_tokens: Optional[int] = None) -> AIResponse:
        raise NotImplementedError 