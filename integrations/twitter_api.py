import requests
from bs4 import BeautifulSoup
from typing import Optional
import re

class TwitterAPI:
    """A simple Twitter API integration for converting threads to markdown."""
    
    def __init__(self):
        self.headers = {
            'Accept': '*/*',
            'X-User-IP': '1.1.1.1',
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15'
        }
        self.nitter_instance = "nitter.net"  # Default nitter instance
    
    def _get_request(self, url: str) -> Optional[requests.Response]:
        """Make an HTTP GET request with proper headers."""
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"Error making request: {e}")
            return None

    def _convert_to_nitter_url(self, url: str) -> str:
        """Convert a Twitter URL to a Nitter URL."""
        return url.replace("twitter.com", self.nitter_instance)

    def thread_to_markdown(self, url: str) -> Optional[str]:
        """
        Convert a Twitter thread to markdown format.
        
        Args:
            url (str): URL of the Twitter thread
            
        Returns:
            str: Markdown formatted string of the thread, or None if conversion fails
        """
        # Convert to nitter URL if it's a Twitter URL
        nitter_url = self._convert_to_nitter_url(url)
        
        # Get the webpage content
        response = self._get_request(nitter_url)
        if not response:
            return None
            
        # Parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        try:
            # Get author information
            username = soup.find('a', class_="username").get_text().strip()
            
            # Get all tweets in the thread
            tweets = soup.find_all('div', class_='tweet-content media-body')
            
            if not tweets:
                return None
                
            # Build markdown content
            markdown_parts = []
            
            # Add author info
            markdown_parts.append(f"# Twitter Thread by {username}\n")
            markdown_parts.append("---\n")
            
            # Add each tweet
            for tweet in tweets:
                tweet_text = tweet.get_text().strip()
                markdown_parts.append(f"{tweet_text}\n\n---\n")
            
            # Add source link
            markdown_parts.append(f"\nSource: {url}")
            
            return "\n".join(markdown_parts)
            
        except Exception as e:
            print(f"Error parsing thread: {e}")
            return None 