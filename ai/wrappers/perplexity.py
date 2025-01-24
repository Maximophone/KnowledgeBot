from .openai import GPTWrapper
from openai import OpenAI

class PerplexityWrapper(GPTWrapper):
    """Wrapper for Perplexity's API which uses OpenAI's API format"""
    
    def __init__(self, api_key: str):
        # Initialize with Perplexity's base URL and API key
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        ) 