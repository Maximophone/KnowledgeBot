from typing import Callable, Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import json

class ToolProvider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"

@dataclass
class ToolParameter:
    """Definition of a single parameter for a tool"""
    type: str  # string, integer, number, boolean
    description: str
    required: bool = True
    enum: Optional[List[str]] = None

@dataclass
class Tool:
    """Represents a tool/function that can be called by AI models"""
    func: Callable
    name: str
    description: str
    parameters: Dict[str, ToolParameter]
    
    def to_provider_schema(self, provider: ToolProvider) -> Dict[str, Any]:
        """Convert tool definition to provider-specific schema"""
        if provider == ToolProvider.ANTHROPIC:
            return {
                "name": self.name,
                "description": self.description,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        name: {
                            "type": param.type,
                            "description": param.description,
                            **({"enum": param.enum} if param.enum else {})
                        }
                        for name, param in self.parameters.items()
                    },
                    "required": [
                        name for name, param in self.parameters.items() 
                        if param.required
                    ]
                }
            }
        elif provider == ToolProvider.OPENAI:
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            name: {
                                "type": param.type,
                                "description": param.description,
                                **({"enum": param.enum} if param.enum else {})
                            }
                            for name, param in self.parameters.items()
                        },
                        "required": [
                            name for name, param in self.parameters.items() 
                            if param.required
                        ]
                    }
                }
            }

@dataclass
class ToolCall:
    """A request from the AI to call a tool"""
    name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None  # For Anthropic
    
    @classmethod
    def from_provider_response(cls, response: Any, provider: ToolProvider) -> Optional['ToolCall']:
        """Create a ToolCall from a provider-specific response"""
        if provider == ToolProvider.ANTHROPIC:
            if response.stop_reason == "tool_use":
                tool_block = next(
                    (block for block in response.content if block["type"] == "tool_use"),
                    None
                )
                if tool_block:
                    return cls(
                        name=tool_block["name"],
                        arguments=tool_block["input"],
                        id=tool_block["id"]
                    )
        elif provider == ToolProvider.OPENAI:
            if response.choices[0].message.function_call:
                func_call = response.choices[0].message.function_call
                return cls(
                    name=func_call.name,
                    arguments=json.loads(func_call.arguments)
                )
        return None

@dataclass
class ToolResult:
    """Result of executing a tool"""
    name: str
    result: Any
    tool_call_id: Optional[str] = None  # For Anthropic
    error: Optional[str] = None
    
    def to_provider_format(self, provider: ToolProvider) -> Dict[str, Any]:
        """Convert result to provider-specific format"""
        if provider == ToolProvider.ANTHROPIC:
            return {
                "type": "tool_result",
                "tool_use_id": self.tool_call_id,
                "content": str(self.result) if not self.error else str(self.error),
                "is_error": bool(self.error)
            }
        elif provider == ToolProvider.OPENAI:
            return {
                "role": "function",
                "name": self.name,
                "content": str(self.result) if not self.error else str(self.error)
            }

def tool(
    description: str,
    parameters: Dict[str, Dict[str, Any]]
) -> Callable:
    """Decorator to convert a function into an AI-callable tool"""
    def decorator(func: Callable) -> Callable:
        # Convert parameter definitions to ToolParameter objects
        tool_params = {
            name: ToolParameter(
                type=param.get("type", "string"),
                description=param.get("description", ""),
                required=param.get("required", True),
                enum=param.get("enum")
            )
            for name, param in parameters.items()
        }
        
        # Create and attach Tool instance
        func.tool = Tool(
            func=func,
            name=func.__name__,
            description=description,
            parameters=tool_params
        )
        return func
    return decorator