from typing import Literal
from ..tools import tool

@tool(
    description="Test method - Fetch weather data for a location",
    city="The city to get weather for",
    units="The temperature units to use",
    safe=True  # This is a read-only operation
)
def test_get_weather(
    city: str,
    units: Literal["celsius", "fahrenheit"] = "celsius"
) -> str:
    return f"The weather in {city} is in {units}."

@tool(
    description="Test method - Unsafe operation that does nothing",
    safe=False  # This is an unsafe operation
)
def test_unsafe_operation() -> str:
    return "This is an unsafe operation that does nothing."


# Export the tools in this toolset
TOOLS = [test_get_weather, test_unsafe_operation] 