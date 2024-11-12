from typing import List, Dict, Tuple
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
    "o1-mini": "o1-mini"
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
                 temperature: float) -> str:
        response = self._messages(model_name, messages, system_prompt, max_tokens, temperature)
        log_token_use(model_name, count_tokens_input(messages, system_prompt))
        log_token_use(model_name, count_tokens_output(response), input=False)
        return response
    
    def _messages(self, model: str, messages: List[Dict[str,str]], system_prompt: str, max_tokens: int, 
                 temperature: float) -> str:
        raise NotImplementedError

class ClaudeWrapper(AIWrapper):
    def __init__(self, api_key: str):
        self.client = anthropic.Client(api_key=api_key)

    def _messages(self, model: str, messages: List[Dict[str,str]], system_prompt: str, max_tokens: int, 
                 temperature: float) -> str:
        message = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages
        )
        return message.content[0].text
    
class GeminiWrapper(AIWrapper):
    def __init__(self, api_key: str, model_name:str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
    
    def _messages(self, model_name: str, messages: List[Dict[str,str]], system_prompt: str, max_tokens: int, 
                 temperature: float) -> str:
        if model_name:
            model = genai.GenerativeModel(model_name)
        else:
            model = self.model
        role_mapping = {"user": "user", "assistant": "model"}
        messages=[{"role": role_mapping.get(m["role"]), "parts":[m["content"]]} for m in messages]
        response = model.generate_content(
            messages
        )
        return response.text
    
class GPTWrapper(AIWrapper):
    def __init__(self, api_key: str, org: str):
        self.client = OpenAI(api_key = api_key, organization=org)

    def _messages(self, model_name: str, messages: List[Dict[str,str]], system_prompt: str, max_tokens: int, 
                 temperature: float) -> str:
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages
        response = self.client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content

class MockWrapper(AIWrapper):
    def __init__(self):
        pass

    def _messages(self, model_name: str, messages: List[Dict[str, str]],
        system_prompt: str, max_tokens: int, temperature:float) -> str:
        response = "---PARAMETERS START---\n"
        response += f"max_tokens: {max_tokens}\n"
        response += f"temperature: {temperature}\n"
        response += "---PARAMETERS END---\n"

        response += "---SYSTEM PROMPT START---\n"
        response += system_prompt + "\n"
        response += "---SYSTEM PROMPT END---\n"

        response += "---MESSAGES START---\n"
        for message in messages:
            response += f"role: {message['role']}\n"
            response += "content: \n"
            response += str(message["content"])
            response += "\n"
        response += "---MESSAGES END---\n"

        return response

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
    def __init__(self, model_name: str, system_prompt: str = "", debug=False):
        self.model_name = get_model(model_name)
        self.client = get_client(model_name)
        self.system_prompt = system_prompt
        self._history = []
        self.debug=debug

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
                image_paths: List[str] = None) -> str:
        messages = self._prepare_messages(message, image_paths)
        response = self.messages(messages, system_prompt, model_override, 
                                 max_tokens, temperature, debug=debug)
        if xml:
            response = f"<response>{response}</response>"
        return response
        
    def messages(self, messages: List[Dict[str, str]], system_prompt: str = None, 
                 model_override: str = None, max_tokens: int = DEFAULT_MAX_TOKENS, 
                 temperature: float = 0.0, xml: bool = False, debug: bool = False) -> str:
        debug = debug | self.debug
        if model_override:
            model_name = get_model(model_override) or self.model_name
            client = get_client(model_override) or self.client
        else:
            model_name = self.model_name
            client = self.client
        system_prompt = system_prompt or self.system_prompt

        if debug:
            print(f"--MODEL: {model_name}--", flush=True)
            print("--SYSTEM PROMPT START--", flush=True)
            print(system_prompt.encode("utf-8"), flush=True)
            print("--SYSTEM PROMPT END--", flush=True)
            print("--MESSAGES RECEIVED START--", flush=True)
            for message in messages:
                print("role: ", message["role"], flush=True)
                if isinstance(message["content"], list):
                    for item in message["content"]:
                        if item["type"] == "text":
                            print("content (text): ", item["text"].encode("utf-8"), flush=True)
                        elif item["type"] == "image":
                            print("content (image): [base64 encoded image]", flush=True)
                else:
                    print("content: ", message["content"].encode("utf-8"), flush=True)
            print("--MESSAGES RECEIVED END--", flush=True)

        response = client.messages(model_name, messages, system_prompt, 
                                   max_tokens, temperature)
        if xml:
            response = f"<response>{response}</response>"
        if debug:
            print("--RESPONSE START--", flush=True)
            print(response.encode("utf-8"), flush=True)
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
                "content": response
            }
        ]
        if xml:
            response = f"<response>{response}</response>"
        return response