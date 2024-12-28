from typing import List, Dict, Tuple, Optional
import anthropic
import google.generativeai as genai
import yaml
from openai import OpenAI
from datetime import datetime as dt
import sys
import PyPDF2
import fitz
import re
import imghdr
import os
import base64
from PIL import Image
from io import BytesIO
from config import secrets
from dataclasses import dataclass
from .tools import Tool, ToolCall, ToolResult
import json

@dataclass
class AIResponse:
    content: str
    tool_calls: Optional[List[ToolCall]] = None

_MODELS_DICT = {
    "mock": "mock-",
    "haiku": "claude-3-haiku-20240307",
    "sonnet": "claude-3-sonnet-20240229",
    "opus": "claude-3-opus-20240229",
    "sonnet3.5": "claude-3-5-sonnet-latest",
    "haiku3.5": "claude-3-5-haiku-latest",
    "gemini1.0": "gemini-1.0-pro-latest",
    "gemini1.5": "gemini-1.5-pro-latest",
    "gpt3.5": "gpt-3.5-turbo",
    "gpt4": "gpt-4-turbo-preview",
    "gpt4o": "gpt-4o",
    "mini": "gpt-4o-mini",
    "o1-preview": "o1-preview",
    "o1-mini": "o1-mini",
    "o1": "o1-2024-12-17"
}

TOKEN_COUNT_FILE = "token_count.csv"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.0

# def extract_text_from_pdf(pdf_path):
#     text = ""
#     with open(pdf_path, 'rb') as file:
#         reader = PyPDF2.PdfReader(file)
#         for page in reader.pages:
#             text += page.extract_text()
#     return text

def get_prompt(prompt_name: str) -> str:
    with open(f"prompts/{prompt_name}.md", "r") as f:
        return f.read()

def encode_image(image_path: str) -> Tuple[str, str]:
    with open(image_path, "rb") as image_file:
        file_content = image_file.read()
        image_type = imghdr.what(None, file_content)
        if image_type is None:
            raise ValueError(f"Unsupported image format for file: {image_path}")
        return base64.b64encode(file_content).decode('utf-8'), f"image/{image_type}"

def validate_image(image_path: str, max_size: int = 20 * 1024 * 1024) -> None:
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    if os.path.getsize(image_path) > max_size:
        raise ValueError(f"Image file too large: {image_path}")
    if imghdr.what(image_path) is None:
        raise ValueError(f"Unsupported image format: {image_path}")

def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            blocks = page.get_text("blocks")
            for block in blocks:
                block_text = block[4]
                # Remove hyphens at the end of lines
                block_text = re.sub(r'-\n', '', block_text)
                # Replace single newlines with spaces, but keep paragraph breaks
                block_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', block_text)
                # Normalize spaces
                block_text = re.sub(r'\s+', ' ', block_text)
                text += block_text.strip() + "\n\n"
    
    # Final cleanup
    text = re.sub(r'\n{3,}', '\n\n', text)  # Replace multiple newlines with double newlines
    text = text.strip()  # Remove leading/trailing whitespace
    
    return text

def n_tokens(text: str) -> int:
    return len(text) // 4

def n_tokens_images(images: List[Dict]) -> int:
    total = 0
    for image in images:
        width, height = get_image_dimensions_from_base64(image["data"])
        total += width*height // 750 # (anthropic's estimation of # of tokens)
    return total

def get_image_dimensions_from_base64(base64_string):
    # Remove the MIME type prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',', 1)[1]
    
    # Decode the base64 string
    image_data = base64.b64decode(base64_string)
    
    # Create a file-like object from the decoded data
    image_file = BytesIO(image_data)
    
    # Open the image using PIL
    with Image.open(image_file) as img:
        # Get the dimensions
        width, height = img.size
    
    return width, height

def count_tokens_input(messages: str, system_prompt: str) -> int:
    text = system_prompt
    images = []
    for m in messages:
        if isinstance(m["content"], str):
            text += m["content"]
        else:
            for content in m["content"]:
                if content["type"] == "text":
                    text += content["text"]
                elif content["type"] == "image":
                    images.append(content["source"])
    return n_tokens(text) + n_tokens_images(images)

def count_tokens_output(response: str):
    return n_tokens(response)

def log_token_use(model: str, n_tokens: int, input: bool = True, 
                  fpath: str=TOKEN_COUNT_FILE):
    t = str(dt.now())
    script = sys.argv[0]
    with open(fpath, "a+") as f:
        if input:
            f.write(f"{model},input,{n_tokens},{t},{script}\n")
        else:
            f.write(f"{model},output,{n_tokens},{t},{script}\n")

class AIWrapper:
    def messages(self, model_name: str, messages: List[Dict[str,str]], 
                 system_prompt: str, max_tokens: int, 
                 temperature: float, tools: Optional[List[Tool]] = None) -> AIResponse:
        response = self._messages(model_name, messages, system_prompt, max_tokens, 
                                temperature, tools)
        log_token_use(model_name, count_tokens_input(messages, system_prompt))
        log_token_use(model_name, count_tokens_output(response.content), input=False)
        return response
    
    def _messages(self, model: str, messages: List[Dict[str,str]], 
                 system_prompt: str, max_tokens: int, 
                 temperature: float, tools: Optional[List[Tool]] = None) -> AIResponse:
        raise NotImplementedError

class ClaudeWrapper(AIWrapper):
    def __init__(self, api_key: str):
        self.client = anthropic.Client(api_key=api_key)

    def _messages(self, model: str, messages: List[Dict[str,str]], 
                 system_prompt: str, max_tokens: int, temperature: float,
                 tools: Optional[List[Tool]] = None) -> AIResponse:
        # Convert tools to Claude's format if provided
        claude_tools = None
        if tools:
            claude_tools = [{
                "name": tool.tool.name,
                "description": tool.tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        name: {
                            "type": param.type,
                            "description": param.description,
                            **({"enum": param.enum} if param.enum else {})
                        }
                        for name, param in tool.tool.parameters.items()
                    },
                    "required": [
                        name for name, param in tool.tool.parameters.items()
                        if param.required
                    ]
                }
            } for tool in tools]

        # Convert messages to Claude's format, including tool results
        claude_messages = []
        for message in messages:
            if message["role"] == "tool":
                tool_result: ToolResult = message["content"]
                claude_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_result.tool_call_id,
                        "content": str(tool_result.result) if tool_result.result is not None 
                                 else f"Error: {tool_result.error}"
                    }]
                })
            else:
                claude_messages.append(message)

        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=claude_messages,
            tools=claude_tools
        )

        # Extract content and any tool calls
        content = ""
        tool_calls = []
        
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input
                ))

        return AIResponse(
            content=content,
            tool_calls=tool_calls if tool_calls else None
        )
    
class GeminiWrapper(AIWrapper):
    def __init__(self, api_key: str, model_name:str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
    
    def _messages(self, model_name: str, messages: List[Dict[str,str]], system_prompt: str, max_tokens: int, 
                 temperature: float, tools: Optional[List[Tool]] = None) -> AIResponse:
        if model_name:
            model = genai.GenerativeModel(model_name)
        else:
            model = self.model
        role_mapping = {"user": "user", "assistant": "model"}
        messages=[{"role": role_mapping.get(m["role"]), "parts":[m["content"]]} for m in messages]
        response = model.generate_content(
            messages
        )
        return AIResponse(content=response.text)
    
class GPTWrapper(AIWrapper):
    def __init__(self, api_key: str, org: str):
        self.client = OpenAI(api_key=api_key, organization=org)

    def _messages(self, model_name: str, messages: List[Dict[str,str]], 
                 system_prompt: str, max_tokens: int, temperature: float,
                 tools: Optional[List[Tool]] = None) -> AIResponse:
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages
            
        # Convert tools to OpenAI's format if provided
        openai_tools = None
        if tools:
            openai_tools = [{
                "type": "function",
                "function": {
                    "name": tool.tool.name,
                    "description": tool.tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            name: {
                                "type": param.type,
                                "description": param.description,
                                **({"enum": param.enum} if param.enum else {})
                            }
                            for name, param in tool.tool.parameters.items()
                        },
                        "required": [
                            name for name, param in tool.tool.parameters.items()
                            if param.required
                        ],
                        "additionalProperties": False
                    }
                }
            } for tool in tools]

        # Convert messages to OpenAI's format, including tool results
        openai_messages = []
        for message in messages:
            if message["role"] == "tool":
                tool_result: ToolResult = message["content"]
                openai_messages.append({
                    "role": "tool",
                    "content": json.dumps({
                        "result": tool_result.result,
                        "error": tool_result.error
                    }),
                    "tool_call_id": tool_result.tool_call_id
                })
            else:
                openai_messages.append(message)

        if model_name.startswith("o1"):
            response = self.client.chat.completions.create(
                model=model_name,
                messages=openai_messages,
                max_completion_tokens=max_tokens,
                tools=openai_tools
            )
        else:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=openai_tools
            )

        # Check if the model wants to use a tool
        if response.choices[0].message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=json.loads(tool_call.function.arguments)
                )
                for tool_call in response.choices[0].message.tool_calls
            ]
            return AIResponse(
                content=response.choices[0].message.content or "",
                tool_calls=tool_calls
            )

        return AIResponse(content=response.choices[0].message.content)

class MockWrapper(AIWrapper):
    def __init__(self):
        pass

    def _messages(self, model_name: str, messages: List[Dict[str, str]],
        system_prompt: str, max_tokens: int, temperature:float, tools: Optional[List[Tool]] = None) -> AIResponse:
        response = "---PARAMETERS START---\n"
        response += f"max_tokens: {max_tokens}\n"
        response += f"temperature: {temperature}\n"
        response += "---PARAMETERS END---\n"

        response += "---SYSTEM PROMPT START---\n"
        response += system_prompt + "\n"
        response += "---SYSTEM PROMPT END---\n"

        if tools:
            response += "---TOOLS START---\n"
            for tool in tools:
                tool = tool.tool
                response += f"Tool: {tool.name}\n"
                response += f"Description: {tool.description}\n"
                response += "Parameters:\n"
                for param_name, param in tool.parameters.items():
                    response += f"  - {param_name}:\n"
                    response += f"    type: {param.type}\n"
                    response += f"    description: {param.description}\n"
                    response += f"    required: {param.required}\n"
                    if param.enum:
                        response += f"    enum: {param.enum}\n"
                response += "\n"
            response += "---TOOLS END---\n"

        response += "---MESSAGES START---\n"
        for message in messages:
            response += f"role: {message['role']}\n"
            response += "content: \n"
            response += str(message["content"])
            response += "\n"
        response += "---MESSAGES END---\n"

        return AIResponse(content=response)

def get_client(model_name: str) -> AIWrapper:
    model_name = get_model(model_name)
    client_name, _ = model_name.split("-", 1)
    if client_name == "claude":
        return ClaudeWrapper(secrets.CLAUDE_API_KEY)
    elif client_name == "gemini":
        return GeminiWrapper(secrets.GEMINI_API_KEY, get_model(model_name))
    elif client_name == "gpt" or client_name == "o1":
        return GPTWrapper(secrets.OPENAI_API_KEY, secrets.OPENAI_ORG)
    elif client_name == "mock":
        return MockWrapper()
    return None
    
def get_model(model_name: str) -> str:
    return _MODELS_DICT.get(model_name, model_name)

class AI:
    def __init__(self, model_name: str, system_prompt: str = "", 
                 tools: Optional[List[Tool]] = None, debug=False):
        self.model_name = get_model(model_name)
        self.client = get_client(model_name)
        self.system_prompt = system_prompt
        self.tools = tools or []
        self._history = []
        self.debug = debug

    def _prepare_messages(self, message: str, image_paths: List[str] = None) -> List[Dict[str, str]]:
        content = []
        if image_paths:
            for image_path in image_paths:
                try:
                    validate_image(image_path)
                    encoded_image, media_type = encode_image(image_path)
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded_image
                        }
                    })
                except (FileNotFoundError, ValueError) as e:
                    print(f"Error processing image {image_path}: {str(e)}")
        
        content.append({
            "type": "text",
            "text": message
        })

        return [{
            "role": "user",
            "content": content if image_paths else message
        }]

    def message(self, message: str, system_prompt: str = None, 
                model_override: str = None, max_tokens: int = DEFAULT_MAX_TOKENS, 
                temperature: float = 0.0, xml: bool = False, debug: bool = False,
                image_paths: List[str] = None, tools: Optional[List[Tool]] = None) -> AIResponse:
        messages = self._prepare_messages(message, image_paths)

        response = self.messages(messages, system_prompt, model_override, 
                               max_tokens, temperature, debug=debug,
                               tools=tools)
        if xml:
            response.content = f"<response>{response.content}</response>"
        return response
        
    def messages(self, messages: List[Dict[str, str]], system_prompt: str = None, 
                 model_override: str = None, max_tokens: int = DEFAULT_MAX_TOKENS, 
                 temperature: float = 0.0, xml: bool = False, debug: bool = False,
                 tools: Optional[List[Tool]] = None) -> AIResponse:
        debug = debug | self.debug
        if model_override:
            model_name = get_model(model_override) or self.model_name
            client = get_client(model_override) or self.client
        else:
            model_name = self.model_name
            client = self.client
        system_prompt = system_prompt or self.system_prompt

        # Merge instance tools with method tools
        tools_to_use = self.tools + (tools or [])

        if debug:
            print(f"--MODEL: {model_name}--", flush=True)
            print("--SYSTEM PROMPT START--", flush=True)
            print(system_prompt.encode("utf-8"), flush=True)
            print("--SYSTEM PROMPT END--", flush=True)
            if tools_to_use:
                print("--TOOLS START--", flush=True)
                for tool in tools_to_use:
                    print(f"Tool: {tool.name} - {tool.description}", flush=True)
                print("--TOOLS END--", flush=True)
            print("--MESSAGES RECEIVED START--", flush=True)
            for message in messages:
                print("role: ", message["role"], flush=True)
                if isinstance(message["content"], list):
                    for item in message["content"]:
                        if item["type"] == "text":
                            print("content (text): ", item["text"].encode("utf-8"), flush=True)
                        elif item["type"] == "image":
                            print("content (image): [base64 encoded image]", flush=True)
                elif isinstance(message["content"], ToolResult):
                    print("content (tool result): ", str(message["content"]), flush=True)
                else:
                    print("content: ", message["content"].encode("utf-8"), flush=True)
            print("--MESSAGES RECEIVED END--", flush=True)

        response = client.messages(model_name, messages, system_prompt, 
                                 max_tokens, temperature, tools=tools_to_use)
            
        if xml:
            response.content = f"<response>{response.content}</response>"
        if debug:
            print("--RESPONSE START--", flush=True)
            print(response.content.encode("utf-8"), flush=True)
            print("--RESPONSE END--", flush=True)
        return response
    
    def conversation(self, message: str, system_prompt: str = None, 
                     model_override: str = None, max_tokens: int = DEFAULT_MAX_TOKENS, 
                     temperature: float = 0.0, xml: bool = False, debug: bool = False,
                     image_paths: List[str] = None):
        messages = self._history + self._prepare_messages(message, image_paths)
        response = self.messages(messages, system_prompt, model_override, max_tokens, temperature, debug=debug)
        self._history = messages + [
            {
                "role": "assistant",
                "content": response.content
            }
        ]
        if xml:
            response.content = f"<response>{response.content}</response>"
        return response