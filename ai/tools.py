from typing import Callable, Dict, Any, List, Optional, get_type_hints, Literal, Union, get_args
from dataclasses import dataclass
import inspect
from enum import Enum

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

@dataclass
class ToolCall:
    """A request from the AI to call a tool"""
    name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None

@dataclass
class ToolResult:
    """Result of executing a tool"""
    name: str
    result: Any
    tool_call_id: Optional[str] = None
    error: Optional[str] = None

def _get_parameter_type(annotation: Any) -> tuple[str, Optional[List[str]]]:
    """Helper to convert Python types to tool parameter types"""
    if annotation == str:
        return "string", None
    elif annotation == int:
        return "integer", None
    elif annotation == float:
        return "number", None
    elif annotation == bool:
        return "boolean", None
    elif hasattr(annotation, "__origin__") and annotation.__origin__ == Literal:
        # Handle Literal types for enums
        enum_values = [str(arg) for arg in get_args(annotation)]
        return "string", enum_values
    elif isinstance(annotation, type) and issubclass(annotation, Enum):
        # Handle Enum classes
        enum_values = [member.name for member in annotation]
        return "string", enum_values
    else:
        return "string", None  # default to string for unknown types

def tool(description: str, **parameter_descriptions: str) -> Callable:
    """
    Decorator to convert a function into an AI-callable tool.
    Only requires a description and parameter descriptions.
    """
    def decorator(func: Callable) -> Callable:
        # Get function signature
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        # Build tool parameters from function signature
        tool_params = {}
        
        for name, param in sig.parameters.items():
            if name not in parameter_descriptions:
                raise ValueError(f"Missing description for parameter '{name}'")
                
            param_type, enum_values = _get_parameter_type(type_hints.get(name, str))
            
            tool_params[name] = ToolParameter(
                type=param_type,
                description=parameter_descriptions[name],
                required=param.default == inspect.Parameter.empty,
                enum=enum_values
            )
        
        # Create and attach Tool instance
        func.tool = Tool(
            func=func,
            name=func.__name__,
            description=description,
            parameters=tool_params
        )
        return func
    return decorator