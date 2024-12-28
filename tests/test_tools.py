import unittest
from unittest.mock import Mock, patch
from ai.tools import (
    Tool, ToolCall, ToolResult, tool, ToolProvider,
    ToolParameter
)

class TestToolParameter(unittest.TestCase):
    def test_tool_parameter_creation(self):
        param = ToolParameter(
            type="string",
            description="Test parameter",
            required=True,
            enum=["a", "b", "c"]
        )
        self.assertEqual(param.type, "string")
        self.assertEqual(param.description, "Test parameter")
        self.assertTrue(param.required)
        self.assertEqual(param.enum, ["a", "b", "c"])

class TestTool(unittest.TestCase):
    def setUp(self):
        self.mock_func = Mock()
        self.tool = Tool(
            func=self.mock_func,
            name="test_tool",
            description="A test tool",
            parameters={
                "param1": ToolParameter(
                    type="string",
                    description="First parameter",
                    required=True
                ),
                "param2": ToolParameter(
                    type="string",
                    description="Second parameter",
                    required=False,
                    enum=["a", "b"]
                )
            }
        )

    def test_anthropic_schema(self):
        schema = self.tool.to_provider_schema(ToolProvider.ANTHROPIC)
        self.assertEqual(schema["name"], "test_tool")
        self.assertEqual(schema["description"], "A test tool")
        self.assertEqual(
            schema["input_schema"]["required"],
            ["param1"]
        )
        self.assertEqual(
            schema["input_schema"]["properties"]["param2"]["enum"],
            ["a", "b"]
        )

    def test_openai_schema(self):
        schema = self.tool.to_provider_schema(ToolProvider.OPENAI)
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "test_tool")
        self.assertEqual(
            schema["function"]["parameters"]["required"],
            ["param1"]
        )

class TestToolCall(unittest.TestCase):
    def test_from_anthropic_response(self):
        mock_response = Mock()
        mock_response.stop_reason = "tool_use"
        mock_response.content = [{
            "type": "tool_use",
            "id": "123",
            "name": "test_tool",
            "input": {"param": "value"}
        }]

        tool_call = ToolCall.from_provider_response(
            mock_response, 
            ToolProvider.ANTHROPIC
        )
        
        self.assertEqual(tool_call.id, "123")
        self.assertEqual(tool_call.name, "test_tool")
        self.assertEqual(tool_call.arguments, {"param": "value"})

    def test_from_openai_response(self):
        mock_message = Mock()
        mock_message.function_call.name = "test_tool"
        mock_message.function_call.arguments = '{"param": "value"}'
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=mock_message)]

        tool_call = ToolCall.from_provider_response(
            mock_response, 
            ToolProvider.OPENAI
        )
        
        self.assertEqual(tool_call.name, "test_tool")
        self.assertEqual(tool_call.arguments, {"param": "value"})

class TestToolResult(unittest.TestCase):
    def test_anthropic_format(self):
        result = ToolResult(
            name="test_tool",
            result="success",
            tool_call_id="123"
        )
        
        formatted = result.to_provider_format(ToolProvider.ANTHROPIC)
        self.assertEqual(formatted["type"], "tool_result")
        self.assertEqual(formatted["tool_use_id"], "123")
        self.assertEqual(formatted["content"], "success")
        self.assertFalse(formatted["is_error"])

    def test_openai_format(self):
        result = ToolResult(
            name="test_tool",
            result="success"
        )
        
        formatted = result.to_provider_format(ToolProvider.OPENAI)
        self.assertEqual(formatted["role"], "function")
        self.assertEqual(formatted["name"], "test_tool")
        self.assertEqual(formatted["content"], "success")

class TestToolDecorator(unittest.TestCase):
    def test_tool_decorator(self):
        @tool(
            description="Test function",
            parameters={
                "param1": {
                    "type": "string",
                    "description": "First param",
                    "required": True
                },
                "param2": {
                    "type": "string",
                    "description": "Second param",
                    "enum": ["a", "b"],
                    "required": False
                }
            }
        )
        def test_func(param1: str, param2: str = "a"):
            return f"{param1} {param2}"

        self.assertTrue(hasattr(test_func, "tool"))
        self.assertIsInstance(test_func.tool, Tool)
        self.assertEqual(test_func.tool.name, "test_func")
        self.assertEqual(test_func.tool.description, "Test function")
        self.assertEqual(len(test_func.tool.parameters), 2)

if __name__ == '__main__':
    unittest.main()