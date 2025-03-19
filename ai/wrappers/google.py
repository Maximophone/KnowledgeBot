import google.generativeai as genai
import logging
import time
from typing import List, Optional
from .base import AIWrapper, AIResponse
from ..types import Message
from ..tools import Tool
from utils.rate_limiter import ReactiveRateLimiter

class GeminiWrapper(AIWrapper):
    def __init__(self, api_key: str, model_name: str, rate_limiting=False, rate_limiter=None):
        """
        Wrapper for Google's Gemini API.
        
        Args:
            api_key: Google API key
            model_name: Gemini model name
            rate_limiting: Whether to enable rate limiting
            rate_limiter: Optional custom rate limiter instance
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting settings
        self.rate_limiting = rate_limiting
        self.rate_limiter = rate_limiter or ReactiveRateLimiter(name=f"gemini_rate_limiter")
        
    
    def _is_rate_limit_error(self, error):
        """
        Check if an exception is a rate limit error.
        
        Args:
            error: Exception to check
            
        Returns:
            bool: True if it's a rate limit error, False otherwise
        """
        # Gemini API might return 429 errors in different ways
        # This handles the common cases
        if hasattr(error, 'status_code') and error.status_code == 429:
            return True
        
        # Check for rate limit messages in the error text
        error_str = str(error).lower()
        rate_limit_phrases = [
            'rate limit', 'rate exceeded', 'too many requests', 
            'resource exhausted', 'quota exceeded', '429'
        ]
        return any(phrase in error_str for phrase in rate_limit_phrases)
    
    def _messages(self, model_name: str, messages: List[Message], 
                 system_prompt: str, max_tokens: int, temperature: float,
                 tools: Optional[List[Tool]] = None,
                 thinking: bool = False, thinking_budget_tokens: Optional[int] = None) -> AIResponse:
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
            
        # Single API call pattern with conditional rate limiting
        while True:
            # Wait if rate limiting is enabled
            if self.rate_limiter:
                self.rate_limiter.wait()
                
            try:
                response = model.generate_content(gemini_messages)
                
                # Record success if rate limiting is enabled
                if self.rate_limiter:
                    self.rate_limiter.record_success()
                    
                return AIResponse(content=response.text)
                
            except Exception as e:
                # Handle rate limit errors if rate limiting is enabled
                if self.rate_limiter and self._is_rate_limit_error(e):
                    self.rate_limiter.record_failure()
                    
                    if self.rate_limiter.exceeded_max_retries():
                        # Get rate limiter status through proper methods
                        status = self.rate_limiter.get_status_info()
                        
                        # Create a more informative error message
                        error_msg = (
                            f"Rate limit exceeded after {status['retry_count']}/{status['max_retries']} retries. "
                            f"Last backoff was {status['current_backoff']:.1f} seconds. "
                            f"Consider waiting or increasing max_retries. Original error: {str(e)}"
                        )
                        self.logger.error(error_msg)
                        
                        # Enhance the original exception with more information
                        if hasattr(e, "__dict__"):
                            e.rate_limit_exceeded = True
                            e.retry_info = status
                        
                        # Re-raise the exception
                        raise
                    
                    # Log retry attempt
                    status = self.rate_limiter.get_status_info()
                    self.logger.warning(f"Rate limit hit, retrying ({status['retry_count']}/{status['max_retries']})")
                    # Continue to next iteration (which will wait due to backoff)
                else:
                    # Not a rate limit error or rate limiting disabled, re-raise
                    raise 