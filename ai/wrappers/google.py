import google.generativeai as genai
from typing import List, Optional
from .base import AIWrapper, AIResponse
from ..types import Message
from ..tools import Tool

class GeminiWrapper(AIWrapper):
    def __init__(self, api_key: str, model_name: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
    
    def _messages(self, model_name: str, messages: List[Message], 
                 system_prompt: str, max_tokens: int, temperature: float,
                 tools: Optional[List[Tool]] = None) -> AIResponse:
        if model_name:
            model = genai.GenerativeModel(model_name)
        else:
            model = self.model

        role_mapping = {"user": "user", "assistant": "model"}
        gemini_messages = []
        for message in messages:
            content = []
            for msg_content in message.content:
                if msg_content.type == "text":
                    content.append(msg_content.text)
                elif msg_content.type == "image":
                    # Gemini expects base64 images in a specific format
                    content.append({
                        "mime_type": msg_content.image["media_type"],
                        "data": msg_content.image["data"]
                    })
            gemini_messages.append({
                "role": role_mapping.get(message.role),
                "parts": content
            })

        response = model.generate_content(gemini_messages)
        return AIResponse(content=response.text) 