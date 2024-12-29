"""
Best practices for tool definitions
To get the best performance out of Claude when using tools, follow these guidelines:

- Provide extremely detailed descriptions. This is by far the most important factor in tool performance. Your descriptions should explain every detail about the tool, including:
    - What the tool does
    - When it should be used (and when it shouldn’t)
    - What each parameter means and how it affects the tool’s behavior
    - Any important caveats or limitations, such as what information the tool does not return if the tool name is unclear. The more context you can give Claude about your tools, the better it will be at deciding when and how to use them. Aim for at least 3-4 sentences per tool description, more if the tool is complex.
- Prioritize descriptions over examples. While you can include examples of how to use a tool in its description or in the accompanying prompt, this is less important than having a clear and comprehensive explanation of the tool’s purpose and parameters. Only add examples after you’ve fully fleshed out the description.

USAGE :

from typing import Literal
from enum import Enum

# Using Literal for enum values
@tool(
    description="Fetch weather data for a location",
    city="The city to get weather for",
    units="The temperature units to use"
)
def get_weather(
    city: str,
    units: Literal["celsius", "fahrenheit"] = "celsius"
) -> str:
    ...

# Using Enum for enum values
class TemperatureUnit(Enum):
    CELSIUS = "C"
    FAHRENHEIT = "F"

@tool(
    description="Fetch weather data for a location",
    city="The city to get weather for",
    units="The temperature units to use"
)
def get_weather_enum(
    city: str,
    units: TemperatureUnit = TemperatureUnit.CELSIUS
) -> str:
    ...

# Regular parameters with defaults
@tool(
    description="Calculate monthly payment for a loan",
    amount="The loan amount",
    rate="Annual interest rate (percentage)",
    years="Loan term in years"
)
def calculate_loan(
    amount: float,
    rate: float,
    years: int = 30
) -> float:
    ...
"""

from typing import Callable, Dict, Any, List, Optional, get_type_hints, Literal, Union, get_args
from dataclasses import dataclass
from enum import Enum
import inspect

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
    safe: bool = False  # True means the tool can be executed without confirmation

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

def tool(
    description: str,
    safe: bool = True,  # New parameter
    **parameter_descriptions: str
) -> Callable:
    """
    Decorator to convert a function into an AI-callable tool.
    
    Args:
        description: Tool description
        safe: Whether the tool can be executed without user confirmation
        **parameter_descriptions: Descriptions for each parameter
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
            parameters=tool_params,
            safe=safe  # Add safety flag to tool
        )
        return func
    return decorator
