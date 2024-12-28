from typing import Literal, Optional, List, Dict
from dataclasses import dataclass
from .tools import ToolCall, ToolResult

@dataclass
class MessageContent:
    type: Literal["text", "tool_use", "tool_result", "image"]
    text: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[ToolResult] = None
    image: Optional[Dict[str, str]] = None

    def __post_init__(self):
        if self.type == "text" and self.text is None:
            raise ValueError("text content must have text field")
        if self.type == "tool_use" and self.tool_call is None:
            raise ValueError("tool_use content must have tool_call field")
        if self.type == "tool_result" and self.tool_result is None:
            raise ValueError("tool_result content must have tool_result field")
        if self.type == "image" and self.image is None:
            raise ValueError("image content must have image field")
        if self.type == "image" and not all(k in self.image for k in ["type", "media_type", "data"]):
            raise ValueError("image field must contain type, media_type, and data")

@dataclass
class Message:
    role: Literal["user", "assistant", "system"]
    content: List[MessageContent]