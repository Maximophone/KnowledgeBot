from typing import List, Optional, Union
from .types import Message, MessageContent
from .tools import Tool
from .models import get_model, get_client
from .image_utils import encode_image, validate_image
from .wrappers import AIResponse

DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.0

def get_prompt(prompt_name: str) -> str:
    with open(f"prompts/{prompt_name}.md", "r") as f:
        return f.read()

class AI:
    def __init__(self, model_name: str, system_prompt: str = "", 
                 tools: Optional[List[Tool]] = None, debug=False):
        self.model_name = get_model(model_name)
        self.client = get_client(model_name)
        self.system_prompt = system_prompt
        self.tools = tools or []
        self._history = []
        self._last_reasoning = None
        self.debug = debug

    def _prepare_messages(self, message: Union[str, Message], image_paths: List[str] = None) -> List[Message]:
        if isinstance(message, Message):
            return [message]
        content = []
        if image_paths:
            for image_path in image_paths:
                try:
                    validate_image(image_path)
                    encoded_image, media_type = encode_image(image_path)
                    content.append(MessageContent(
                        type="image",
                        text=None,
                        tool_call=None,
                        tool_result=None,
                        image={
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded_image
                        }
                    ))
                except (FileNotFoundError, ValueError) as e:
                    print(f"Error processing image {image_path}: {str(e)}")
        
        content.append(MessageContent(
            type="text",
            text=message
        ))

        return [Message(
            role="user",
            content=content
        )]

    def message(self, message: Union[str, Message], system_prompt: str = None, 
                model_override: str = None, max_tokens: int = DEFAULT_MAX_TOKENS, 
                temperature: float = 0.0, xml: bool = False, debug: bool = False,
                image_paths: List[str] = None, tools: Optional[List[Tool]] = None,
                thinking: bool = False, thinking_budget_tokens: Optional[int] = None) -> AIResponse:
        messages = self._prepare_messages(message, image_paths)

        response = self.messages(messages, system_prompt, model_override, 
                               max_tokens, temperature, debug=debug,
                               tools=tools, thinking=thinking, 
                               thinking_budget_tokens=thinking_budget_tokens)
        if xml:
            response.content = f"<response>{response.content}</response>"
        return response
        
    def messages(self, messages: List[Message], system_prompt: str = None, 
                 model_override: str = None, max_tokens: int = DEFAULT_MAX_TOKENS, 
                 temperature: float = 0.0, xml: bool = False, debug: bool = False,
                 tools: Optional[List[Tool]] = None, thinking: bool = False,
                 thinking_budget_tokens: Optional[int] = None) -> AIResponse:
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
                print("role: ", message.role, flush=True)
                for content in message.content:
                    if content.type == "text":
                        print("content (text): ", content.text.encode("utf-8"), flush=True)
                    elif content.type == "image":
                        print("content (image): [base64 encoded image]", flush=True)
                    elif content.type == "tool_result":
                        print("content (tool result): ", str(content.tool_result), flush=True)
            print("--MESSAGES RECEIVED END--", flush=True)
            if thinking:
                print(f"--THINKING: Enabled (budget: {thinking_budget_tokens or 'auto'})--", flush=True)

        response = client.messages(model_name, messages, system_prompt, 
                                 max_tokens, temperature, tools=tools_to_use,
                                 thinking=thinking, thinking_budget_tokens=thinking_budget_tokens)
            
        if xml:
            response.content = f"<response>{response.content}</response>"
        if debug:
            print("--RESPONSE START--", flush=True)
            print(response.content.encode("utf-8"), flush=True)
            print("--RESPONSE END--", flush=True)
            if response.reasoning:
                print("--REASONING START--", flush=True)
                print(response.reasoning[:500] + ("..." if len(response.reasoning) > 500 else ""), flush=True)
                print("--REASONING END--", flush=True)
        return response
    
    def conversation(self, message: str, system_prompt: str = None, 
                     model_override: str = None, max_tokens: int = DEFAULT_MAX_TOKENS, 
                     temperature: float = 0.0, xml: bool = False, debug: bool = False,
                     image_paths: List[str] = None, thinking: bool = False,
                     thinking_budget_tokens: Optional[int] = None):
        messages = self._history + self._prepare_messages(message, image_paths)
        response = self.messages(messages, system_prompt, model_override, max_tokens, 
                               temperature, debug=debug, thinking=thinking,
                               thinking_budget_tokens=thinking_budget_tokens)
        
        # Create assistant message content
        assistant_content = [MessageContent(
            type="text",
            text=response.content
        )]
        
        # Store the conversation history
        self._history = messages + [Message(
            role="assistant",
            content=assistant_content
        )]
        
        # Store reasoning separately if available (not part of the conversation history)
        if response.reasoning:
            self._last_reasoning = response.reasoning
        else:
            self._last_reasoning = None
        
        if xml:
            response.content = f"<response>{response.content}</response>"
        return response