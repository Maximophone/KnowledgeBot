import requests
from typing import Dict, Optional
from urllib.parse import urlparse
from config.secrets import HTML_TO_MARKDOWN_API_KEY

class HTMLToMarkdown:
    """A client for the HTML-to-Markdown API service."""
    
    def __init__(self):
        self.api_key = HTML_TO_MARKDOWN_API_KEY
        self.base_url = "https://api.html-to-markdown.com/v1"
        
    def convert(self, html: str, domain: Optional[str] = None, plugins: Optional[Dict] = None) -> str:
        """
        Convert HTML to Markdown using the API.
        
        Args:
            html: The HTML content to convert
            domain: Optional domain for converting relative links to absolute
            plugins: Optional dictionary of plugins to enable
            
        Returns:
            str: The converted markdown text
            
        Raises:
            Exception: If the API request fails
        """
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        payload = {"html": html}
        if domain:
            payload["domain"] = domain
        if plugins:
            payload["plugins"] = plugins
            
        response = requests.post(
            f"{self.base_url}/convert",
            headers=headers,
            json=payload
        )
        
        if not response.ok:
            error = response.json().get("error", {})
            raise Exception(f"API Error: {error.get('title', 'Unknown error')}")
            
        return response.json()["markdown"]

    def convert_url(self, url: str, plugins: Optional[Dict] = None) -> str:
        """
        Fetch HTML from a URL and convert it to Markdown.
        Automatically handles domain resolution for relative links.
        
        Args:
            url: The URL to fetch and convert
            plugins: Optional dictionary of plugins to enable
            
        Returns:
            str: The converted markdown text
            
        Raises:
            Exception: If the URL fetch fails or if the conversion fails
        """
        try:
            response = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            })
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch URL: {str(e)}")

        # Extract domain for handling relative links
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        return self.convert(response.text, domain=domain, plugins=plugins) 