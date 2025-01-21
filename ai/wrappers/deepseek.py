from .openai import GPTWrapper
from openai import OpenAI

class DeepSeekWrapper(GPTWrapper):
    """Wrapper for DeepSeek's API which uses OpenAI's API format"""
    
    def __init__(self, api_key: str):
        # Initialize with DeepSeek's base URL and API key
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        ) 