from typing import List, Dict
import anthropic
import google.generativeai as genai
import yaml
from openai import OpenAI


with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

_MODELS_DICT = {
    "haiku": "claude-3-haiku-20240307",
    "sonnet": "claude-3-sonnet-20240229",
    "opus": "claude-3-opus-20240229",
    "gemini1.0": "gemini-1.0-pro-latest",
    "gemini1.5": "gemini-1.5-pro-latest",
    "gpt3.5": "gpt-3.5-turbo",
    "gpt4": "gpt-4-turbo-preview"
}

class AIWrapper:
    def messages(self, messages: List[Dict[str,str]], system_prompt: str, max_tokens: int, 
                 temperature: float) -> str:
        pass

class ClaudeWrapper(AIWrapper):
    def __init__(self, api_key: str):
        self.client = anthropic.Client(api_key=api_key)

    def messages(self, model: str, messages: List[Dict[str,str]], system_prompt: str, max_tokens: int, 
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
    
    def messages(self, model_name: str, messages: List[Dict[str,str]], system_prompt: str, max_tokens: int, 
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

    def messages(self, model_name: str, messages: List[Dict[str,str]], system_prompt: str, max_tokens: int, 
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

def get_client(model_name: str) -> AIWrapper:
    model_name = get_model(model_name)
    client_name, _ = model_name.split("-", 1)
    if client_name == "claude":
        return ClaudeWrapper(secrets["claude_api_key"])
    elif client_name == "gemini":
        return GeminiWrapper(secrets["gemini_api_key"], get_model(model_name))
    elif client_name == "gpt":
        return GPTWrapper(secrets["openai_api_key"], secrets["openai_org"])
    return None
    
def get_model(model_name: str) -> str:
    return _MODELS_DICT.get(model_name, model_name)

class AI:
    def __init__(self, model_name: str, system_prompt: str = ""):
        self.model_name = get_model(model_name)
        self.client = get_client(model_name)
        self.system_prompt = system_prompt

    def message(self, message: str, system_prompt: str = None, 
                model_override: str=None, max_tokens: int=1000, 
                temperature: float=0.0) -> str:
        messages = [{
            "role": "user",
            "content": message
        }]
        return self.conversation(messages, system_prompt, model_override, 
                                 max_tokens, temperature)
        
    def conversation(self, messages: List[Dict[str, str]], system_prompt: str = None, 
                     model_override: str = None, max_tokens: int=1000, 
                     temperature: float=0.0) -> str:
        if model_override:
            model_name = get_model(model_override) or self.model_name
            client = get_client(model_override) or self.client
        else:
            model_name = self.model_name
            client = self.client
        system_prompt = system_prompt or self.system_prompt

        response = client.messages(model_name, messages, system_prompt, 
                                   max_tokens, temperature)

        return response


class Claude:
    def __init__(self, client, model: str, system_prompt: str = ""):
        self.client = client
        self.model = self.get_model(model)
        self.system_prompt = system_prompt
        self.history = []

    def get_model(self, model: str) -> str:
        if model == "haiku":
            return "claude-3-haiku-20240307"
        elif model == "sonnet":
            return "claude-3-sonnet-20240229"
        elif model == "opus":
            return "claude-3-opus-20240229"
        else:
            raise Exception(f"Unknown Model: {model}")
        
    def conversation(self, messages: List[Dict[str, str]], model_override=None, max_tokens: int=1000, temperature: float=0.0) -> str:
        model = self.get_model(model_override) if model_override else self.model
        message = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=self.system_prompt,
            messages=messages
        )
        return message.content[0].text

    def message(self, txt: str, model_override=None, max_tokens: int=1000, temperature: float=0.0) -> str:
        model = self.get_model(model_override) if model_override else self.model
        self.history.append(
            {
                "type": "query",
                "content": txt
            }
        )
        message = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": txt}
            ]
        )
        self.history.append(
            {
                "type": "response",
                "content": message.content[0].text
            }
        )
        return message.content[0].text
