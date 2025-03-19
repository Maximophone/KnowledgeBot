import requests
from bs4 import BeautifulSoup
from typing import Optional
import re
import random

class TwitterAPI:
    """A simple Twitter API integration for converting threads to markdown."""
    
    def __init__(self):
        # List of common user agents
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
        ]
        self.nitter_instances = [
            "nitter.net",
            "nitter.poast.org"
        ]
    
    def _get_random_user_agent(self) -> str:
        """Get a random user agent from the list."""
        return random.choice(self.user_agents)
    
    def _get_request(self, url: str) -> Optional[requests.Response]:
        """Make an HTTP GET request with proper headers."""
        try:
            # Use a different proxy service format
            proxy_url = f"https://api.allorigins.win/get?url={requests.utils.quote(url)}&contentType=text/html"
            
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'User-Agent': self._get_random_user_agent()
            }
            
            print(f"\nMaking request through proxy: {proxy_url}")
            response = requests.get(proxy_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Print response info for debugging
            print(f"\nResponse status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            # Parse the JSON response from the proxy
            json_response = response.json()
            
            if not json_response.get('contents'):
                print("Empty response content")
                return None
                
            # Create a new response object with the HTML content
            html_response = requests.Response()
            html_response._content = json_response['contents'].encode('utf-8')
            html_response.status_code = 200
            
            # Print first few characters of response
            print(f"\nResponse preview: {json_response['contents'][:200]}...")
            
            return html_response
            
        except requests.RequestException as e:
            print(f"Error making request: {e}")
            return None
        except ValueError as e:
            print(f"Error parsing JSON response: {e}")
            return None

    def _convert_to_nitter_url(self, url: str, instance: str) -> str:
        """Convert a Twitter/X URL to a Nitter URL using the specified instance."""
        return url.replace("twitter.com", instance).replace("x.com", instance)

    def thread_to_markdown(self, url: str) -> Optional[str]:
        """
        Convert a Twitter thread to markdown format.
        
        Args:
            url (str): URL of the Twitter thread
            
        Returns:
            str: Markdown formatted string of the thread, or None if conversion fails
        """
        # Try each Nitter instance until one works
        for instance in self.nitter_instances:
            print(f"\nTrying Nitter instance: {instance}")
            nitter_url = self._convert_to_nitter_url(url, instance)
            print(f"Fetching from URL: {nitter_url}")
            
            # Get the webpage content
            response = self._get_request(nitter_url)
            if not response:
                print(f"Failed to get response from {instance}, trying next instance...")
                continue
                
            # Parse the HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            try:
                # Print all div classes for debugging
                print("\nAll div classes found:")
                divs_with_class = [div for div in soup.find_all('div') if div.get('class')]
                if not divs_with_class:
                    print("No divs with classes found in the HTML")
                    print("\nFirst 500 chars of HTML:")
                    print(soup.prettify()[:500])
                    continue
                    
                for div in divs_with_class:
                    print(f"Found div with classes: {div['class']}")
                
                # Try to find the container directly
                container = soup.find('div', class_='container')
                if not container:
                    print("\nCould not find container div")
                    print("\nFirst level divs in the document:")
                    for div in soup.find_all('div', recursive=False):
                        print(f"Found top-level div: {div.get('class', ['no-class'])}")
                    continue
                    
                conversation = container.find('div', class_='conversation')
                if not conversation:
                    print("Could not find conversation div")
                    print("\nDivs inside container:")
                    for div in container.find_all('div', recursive=False):
                        print(f"Found container child div: {div.get('class', ['no-class'])}")
                    continue
                    
                main_thread = conversation.find('div', class_='main-thread')
                if not main_thread:
                    print("Could not find main-thread div")
                    print("\nDivs inside conversation:")
                    for div in conversation.find_all('div', recursive=False):
                        print(f"Found conversation child div: {div.get('class', ['no-class'])}")
                    continue
                
                # Find the timeline items (tweets)
                timeline_items = main_thread.find_all('div', class_='timeline-item')
                if not timeline_items:
                    print("Could not find timeline items")
                    continue
                
                # Get author information from the first tweet
                first_tweet = timeline_items[0]
                tweet_header = first_tweet.find('div', class_='tweet-header')
                if not tweet_header:
                    print("Could not find tweet-header div")
                    continue
                    
                username = None
                fullname = None
                
                # Get the username and fullname
                fullname_elem = tweet_header.find('a', class_='fullname')
                username_elem = tweet_header.find('a', class_='username')
                
                if fullname_elem and username_elem:
                    fullname = fullname_elem.get_text().strip()
                    username = username_elem.get_text().strip()
                else:
                    print("Could not find fullname or username elements")
                    print(f"Tweet header HTML: {tweet_header}")
                    continue
                
                if not username:
                    print("Could not find username")
                    continue
                
                # Get all tweets in the thread
                tweets = []
                
                # Process each timeline item
                for item in timeline_items:
                    tweet_content = item.find('div', class_='tweet-content media-body')
                    if tweet_content:
                        tweets.append(tweet_content)
                
                if not tweets:
                    print("Could not find any tweets")
                    continue
                    
                # Build markdown content
                markdown_parts = []
                
                # Add author info
                markdown_parts.append(f"# Twitter Thread by {fullname} ({username})\n")
                markdown_parts.append("---\n")
                
                # Add each tweet
                for tweet in tweets:
                    tweet_text = tweet.get_text().strip()
                    # Clean up the text - remove extra whitespace and newlines
                    tweet_text = re.sub(r'\s+', ' ', tweet_text)
                    # Remove any "x/y" thread markers at the end
                    tweet_text = re.sub(r'\s*\d+/\d+\s*$', '', tweet_text)
                    markdown_parts.append(f"{tweet_text}\n\n---\n")
                
                # Add source link
                markdown_parts.append(f"\nSource: {url}")
                
                return "\n".join(markdown_parts)
                
            except Exception as e:
                print(f"Error parsing thread from {instance}: {e}")
                print("\nFull HTML content:")
                print(soup.prettify()[:1000])
                continue
        
        print("\nAll Nitter instances failed")
        return None 