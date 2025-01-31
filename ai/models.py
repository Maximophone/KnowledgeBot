from config import secrets
from .wrappers import ClaudeWrapper, GeminiWrapper, GPTWrapper, MockWrapper, AIWrapper, DeepSeekWrapper, PerplexityWrapper

_MODELS_DICT = {
    "mock": "mock-",
    "haiku": "claude-3-haiku-20240307",
    "sonnet": "claude-3-sonnet-20240229",
    "opus": "claude-3-opus-20240229",
    "sonnet3.5": "claude-3-5-sonnet-latest",
    "haiku3.5": "claude-3-5-haiku-latest",
    "gemini1.0": "gemini-1.0-pro-latest",
    "gemini1.5": "gemini-1.5-pro-latest",
    "gemini2.0flash": "gemini-2.0-flash-exp",
    "gemini2.0flashthinking": "gemini-2.0-flash-thinking-exp",
    "gemini2.0exp": "gemini-exp-1206",
    "gpt3.5": "gpt-3.5-turbo",
    "gpt4": "gpt-4-turbo-preview",
    "gpt4o": "gpt-4o",
    "mini": "gpt-4o-mini",
    "o1-preview": "o1-preview",
    "o1-mini": "o1-mini",
    "o1": "o1-2024-12-17",
    "deepseek-chat": "deepseek-chat",
    "deepseek-reasoner": "deepseek-reasoner",
    "sonar": "sonar",
    "sonar-pro": "sonar-pro",
}

def get_model(model_name: str) -> str:
    return _MODELS_DICT.get(model_name, model_name)

def get_client(model_name: str) -> AIWrapper:
    model_name = get_model(model_name)
    client_name, _ = model_name.split("-", 1) if "-" in model_name else (model_name, "")
    if client_name == "claude":
        return ClaudeWrapper(secrets.CLAUDE_API_KEY)
    elif client_name == "gemini":
        return GeminiWrapper(secrets.GEMINI_API_KEY, get_model(model_name))
    elif client_name == "gpt" or client_name == "o1":
        return GPTWrapper(secrets.OPENAI_API_KEY, secrets.OPENAI_ORG)
    elif client_name == "deepseek":
        return DeepSeekWrapper(secrets.DEEPSEEK_API_KEY)
    elif client_name == "sonar":
        return PerplexityWrapper(secrets.PERPLEXITY_API_KEY)
    elif client_name == "mock":
        return MockWrapper()
    return None 