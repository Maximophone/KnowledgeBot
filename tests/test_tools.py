import unittest
from typing import Literal
from enum import Enum
from ai_core.tools import tool, Tool, ToolParameter, ToolCall, ToolResult

class TestToolDecorator(unittest.TestCase):
    def test_basic_types(self):
        @tool(
            description="Test function with basic types",
            name="The person's name",
            age="The person's age",
            height="The person's height",
            is_student="Whether the person is a student"
        )
        def person_info(
            name: str,
            age: int,
            height: float,
            is_student: bool = False
        ) -> str:
            return f"{name}, {age}, {height}, {is_student}"

        self.assertTrue(hasattr(person_info, "tool"))
        tool_obj = person_info.tool
        
        # Check basic tool attributes
        self.assertEqual(tool_obj.name, "person_info")
        self.assertEqual(tool_obj.description, "Test function with basic types")
        
        # Check parameters
        params = tool_obj.parameters
        self.assertEqual(len(params), 4)
        
        # Check string parameter
        self.assertEqual(params["name"].type, "string")
        self.assertEqual(params["name"].description, "The person's name")
        self.assertTrue(params["name"].required)
        self.assertIsNone(params["name"].enum)
        
        # Check integer parameter
        self.assertEqual(params["age"].type, "integer")
        self.assertTrue(params["age"].required)
        
        # Check float parameter
        self.assertEqual(params["height"].type, "number")
        self.assertTrue(params["height"].required)
        
        # Check boolean parameter with default
        self.assertEqual(params["is_student"].type, "boolean")
        self.assertFalse(params["is_student"].required)

    def test_literal_enum(self):
        @tool(
            description="Test function with literal enum",
            color="The color to use",
            size="The size option"
        )
        def style_config(
            color: Literal["red", "blue", "green"],
            size: Literal["small", "medium", "large"] = "medium"
        ) -> None:
            pass

        tool_obj = style_config.tool
        params = tool_obj.parameters
        
        # Check color parameter
        self.assertEqual(params["color"].type, "string")
        self.assertEqual(params["color"].enum, ["red", "blue", "green"])
        self.assertTrue(params["color"].required)
        
        # Check size parameter
        self.assertEqual(params["size"].type, "string")
        self.assertEqual(params["size"].enum, ["small", "medium", "large"])
        self.assertFalse(params["size"].required)

    def test_enum_class(self):
        class Direction(Enum):
            NORTH = "N"
            SOUTH = "S"
            EAST = "E"
            WEST = "W"

        @tool(
            description="Test function with enum class",
            direction="The direction to move",
            steps="Number of steps"
        )
        def move(direction: Direction, steps: int = 1) -> None:
            pass

        tool_obj = move.tool
        params = tool_obj.parameters
        
        # Check direction parameter
        self.assertEqual(params["direction"].type, "string")
        self.assertEqual(
            set(params["direction"].enum),
            {"NORTH", "SOUTH", "EAST", "WEST"}
        )
        self.assertTrue(params["direction"].required)

    def test_missing_description(self):
        with self.assertRaises(ValueError):
            @tool(
                description="Test function",
                param1="First parameter"
                # Missing description for param2
            )
            def test_func(param1: str, param2: int):
                pass

class TestToolCall(unittest.TestCase):
    def test_tool_call_creation(self):
        tool_call = ToolCall(
            name="test_tool",
            arguments={"param": "value"},
            id="123"
        )
        
        self.assertEqual(tool_call.name, "test_tool")
        self.assertEqual(tool_call.arguments, {"param": "value"})
        self.assertEqual(tool_call.id, "123")

class TestToolResult(unittest.TestCase):
    def test_success_result(self):
        result = ToolResult(
            name="test_tool",
            result="success",
            tool_call_id="123"
        )
        
        self.assertEqual(result.name, "test_tool")
        self.assertEqual(result.result, "success")
        self.assertEqual(result.tool_call_id, "123")
        self.assertIsNone(result.error)

    def test_error_result(self):
        result = ToolResult(
            name="test_tool",
            result=None,
            error="Operation failed"
        )
        
        self.assertEqual(result.name, "test_tool")
        self.assertIsNone(result.result)
        self.assertEqual(result.error, "Operation failed")

if __name__ == '__main__':
    unittest.main()