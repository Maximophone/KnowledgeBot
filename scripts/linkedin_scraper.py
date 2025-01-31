"""Script to scrape LinkedIn profiles and save them locally."""

from scripts.base_script import BaseScript
from integrations.linkedin_client import get_linkedin_client
from config.secrets import LINKEDIN_EMAIL, LINKEDIN_PASSWORD
from config.linkedin_config import MY_PROFILE_ID, MY_PROFILE_URN
from utils.rate_limiter import RateLimiter
from typing import List, Optional, Literal
from pathlib import Path
import logging
import argparse
import json
import traceback
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class LinkedInScraper(BaseScript):
    def __init__(self):
        # Initialize name first since BaseScript needs it
        self._name = "linkedin_scraper"
        super().__init__()
        self.client = get_linkedin_client(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
        
        # Initialize rate limiter for LinkedIn API calls
        self.rate_limiter = RateLimiter(
            name="linkedin_api",
            min_delay_seconds=10.0,  # Minimum 10 seconds between calls
            max_delay_seconds=20.0,  # Add up to 10 seconds of jitter
            max_per_day=1000
        )
        
        # Default profile refresh age in days
        self.profile_refresh_days = 60
        
        # Create subdirectories for different types of data
        self.profiles_dir = self.output_dir / "profiles"
        self.connections_dir = self.output_dir / "connections"
        self.search_dir = self.output_dir / "search"
        self.conversations_dir = self.output_dir / "conversations"
        self.posts_dir = self.output_dir / "posts"
        
        for directory in [self.profiles_dir, self.connections_dir, 
                         self.conversations_dir, self.posts_dir, self.search_dir]:
            directory.mkdir(exist_ok=True)
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return "Scrapes LinkedIn data including profiles, connections, and conversations"
    
    def _needs_profile_update(self, file_id: str) -> bool:
        """Check if a profile needs to be updated based on its age
        
        Args:
            file_id: The profile ID or URN used in the filename
            
        Returns:
            bool: True if profile should be updated, False otherwise
        """
        try:
            # Look for any existing profile files with this ID
            existing_files = list(self.profiles_dir.glob(f"{file_id}_*.json"))
            if not existing_files:
                return True
                
            # Get the most recent file
            latest_file = max(existing_files, key=lambda p: p.stat().st_mtime)
            
            # Check if file is older than refresh threshold
            file_age_days = (datetime.now().timestamp() - latest_file.stat().st_mtime) / (24 * 3600)
            return file_age_days >= self.profile_refresh_days
            
        except Exception as e:
            logger.error(f"Error checking profile age for {file_id}: {str(e)}")
            # If there's any error checking the file, assume we should update
            return True
    
    def scrape_profile(self, profile_id: str = None, profile_urn: str = None) -> dict:
        """Scrape a single profile and save it to its own file
        
        Args:
            profile_id: Public identifier of the LinkedIn profile
            profile_urn: URN identifier of the LinkedIn profile
        """
        try:
            # Use profile_id if available, otherwise use the URN
            file_id = profile_id or profile_urn
            
            # Check if we need to update this profile
            if not self._needs_profile_update(file_id):
                logger.info(f"Profile {file_id} is up to date, skipping...")
                # Find and return the most recent profile data
                existing_files = list(self.profiles_dir.glob(f"{file_id}_*.json"))
                latest_file = max(existing_files, key=lambda p: p.stat().st_mtime)
                with open(latest_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            profile_json = self.client.get_profile(
                public_id=profile_id,
                urn_id=profile_urn
            )
            if profile_json:
                self.save_json_output(profile_json, f"profiles/{file_id}")
            return profile_json
        except Exception as e:
            logger.error(f"Failed to scrape profile {profile_id or profile_urn}: {str(e)}\n{traceback.format_exc()}")
            return {}
    
    def scrape_connections(self, profile_urn: str = MY_PROFILE_URN, profile_id: str = MY_PROFILE_ID) -> dict:
        """Scrape connections for a profile and save them"""
        try:
            connections_json = self.client.get_profile_connections(urn_id=profile_urn)
            if connections_json:
                self.save_json_output(
                    connections_json,
                    f"connections/{profile_id}_connections"
                )
            return connections_json
        except Exception as e:
            logger.error(f"Failed to scrape connections for {profile_id}: {str(e)}\n{traceback.format_exc()}")
            return {}
    
    def scrape_conversations(self) -> dict:
        """Scrape all conversations and their details"""
        try:
            # Get list of conversations
            conversations_json = self.client.get_conversations()
            self.save_json_output(conversations_json, "conversations/conversations")
            return conversations_json
        except Exception as e:
            logger.error(f"Failed to scrape conversations: {str(e)}\n{traceback.format_exc()}")
            return {}

    def scrape_search_connections(self, keywords: str) -> dict:
        """Search within connections using keywords and save results
        
        Args:
            keywords: Search terms to find in connection profiles
        """
        try:
            # Search for people with keywords, limiting to 1st connections
            results_json = self.client.search_people(
                keywords=keywords,
                network_depths=["F"],  # F = 1st connections
                limit=1000  # Get a large sample
            )
            
            if results_json:
                # Create filename using sanitized keywords
                safe_keywords = keywords.replace(" ", "_").lower()
                self.save_json_output(results_json, f"search/{safe_keywords}")
            return results_json
        except Exception as e:
            logger.error(f"Failed to search connections for '{keywords}': {str(e)}\n{traceback.format_exc()}")
            return {}

    def scrape_profiles(self, profile_ids: List[str] = None, profile_urns: List[str] = None,
                     profile_data: List[dict] = None) -> List[dict]:
        """Scrape one or multiple profiles and save them to individual files
        
        Args:
            profile_ids: List of LinkedIn profile IDs to scrape
            profile_urns: List of LinkedIn profile URNs to scrape
            profile_data: List of dicts containing profile_id and/or profile_urn for each profile
        """
        results = []
        
        # Handle new profile data format
        if profile_data:
            for profile in profile_data:
                self.rate_limiter.wait()
                profile_id = profile.get('profile_id')
                profile_urn = profile.get('profile_urn')
                if profile_id or profile_urn:
                    result = self.scrape_profile(
                        profile_id=profile_id,
                        profile_urn=profile_urn
                    )
                    results.append(result)
            return results
        
        # Legacy support for separate lists
        if profile_ids:
            for profile_id in profile_ids:
                # Apply rate limiting before each API call
                self.rate_limiter.wait()
                result = self.scrape_profile(profile_id=profile_id)
                results.append(result)
        
        if profile_urns:
            for profile_urn in profile_urns:
                # Apply rate limiting before each API call
                self.rate_limiter.wait()
                result = self.scrape_profile(profile_urn=profile_urn)
                results.append(result)
                
        return results

    def simplify_conversation(self, conversation: dict) -> dict:
        """Extract essential information from a conversation for analysis
        
        Args:
            conversation: Raw conversation details from LinkedIn API
            
        Returns:
            dict: Simplified conversation data with key information
        """
        try:
            # Extract unique participants from messages
            participants = {}
            messages = []
            
            # Process each message in the conversation
            for event in conversation.get('elements', []):
                # Get sender info
                sender = event.get('from', {}).get('com.linkedin.voyager.messaging.MessagingMember', {})
                profile = sender.get('miniProfile', {})
                
                # Add to participants if not seen before
                profile_urn = profile.get('entityUrn', '')
                if profile_urn and profile_urn not in participants:
                    participants[profile_urn] = {
                        'name': f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
                        'profile_urn': profile_urn,
                        'occupation': profile.get('occupation', ''),
                        'public_identifier': profile.get('publicIdentifier', '')
                    }
                
                # Extract message content
                message_content = event.get('eventContent', {}).get('com.linkedin.voyager.messaging.event.MessageEvent')
                if message_content:
                    # Prioritize attributedBody (richer format) over body (plain text)
                    message_text = (
                        message_content.get('body', '') if not message_content.get('attributedBody') 
                        else message_content.get('attributedBody', {}).get('text', '')
                    )
                    
                    # Convert timestamp (milliseconds since epoch) to datetime string
                    timestamp = event.get('createdAt')
                    datetime_str = None
                    if timestamp:
                        try:
                            dt = datetime.fromtimestamp(timestamp / 1000)  # Convert ms to seconds
                            datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            logger.error(f"Failed to convert timestamp {timestamp}: {str(e)}")
                    
                    messages.append({
                        'timestamp': timestamp,
                        'datetime': datetime_str,
                        'sender_name': f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
                        'sender_urn': profile_urn,
                        'message': message_text,
                        'reactions': event.get('reactionSummaries', []),
                        'message_urn': event.get('entityUrn', '')
                    })

            # Sort messages by timestamp (oldest first)
            messages.sort(key=lambda x: x['timestamp'] or 0)

            # Create simplified conversation object
            simplified = {
                'participants': list(participants.values()),
                'messages': messages,
                'metadata': {
                    'total_messages': len(messages),
                    'paging': conversation.get('paging', {}),
                    'first_message_time': messages[0]['datetime'] if messages else None,
                    'last_message_time': messages[-1]['datetime'] if messages else None
                }
            }
            return simplified
        except Exception as e:
            logger.error(f"Failed to simplify conversation: {str(e)}")
            return {}

    def extract_conversation_id(self, full_urn: str) -> str:
        """Extract the conversation ID from a full LinkedIn URN
        
        Args:
            full_urn: Full URN (e.g., "urn:li:fs_conversation:2-MzFlNGQzNmEtNTZlZi00NTUyLTk4ZGUtYmEzMWIzNTJmZjIyXzAxMg==")
            
        Returns:
            str: Conversation ID (e.g., "2-MzFlNGQzNmEtNTZlZi00NTUyLTk4ZGUtYmEzMWIzNTJmZjIyXzAxMg==")
        """
        try:
            return full_urn.split('fs_conversation:')[-1]
        except Exception as e:
            logger.error(f"Failed to parse conversation URN {full_urn}: {str(e)}")
            return None

    def scrape_specific_conversations(self, profile_urns: List[str] = None,
                                    profile_data: List[dict] = None) -> List[dict]:
        """Scrape conversations with specific profiles and save them
        
        Args:
            profile_urns: List of LinkedIn profile URNs
            profile_data: List of dicts containing profile_id and/or profile_urn for each profile
        """
        try:
            results = []
            
            # Get list of URNs to process
            urns_to_process = []
            if profile_data:
                urns_to_process = [p['profile_urn'] for p in profile_data if 'profile_urn' in p]
            elif profile_urns:
                urns_to_process = profile_urns
                
            for profile_urn in urns_to_process:
                self.rate_limiter.wait()
                try:
                    # First get conversation details to get the conversation URN
                    conversation_details = self.client.get_conversation_details(profile_urn)
                    if conversation_details:
                        # Save conversation details
                        self.save_json_output(
                            conversation_details,
                            f"conversations/conversation_details_{profile_urn}"
                        )
                        
                        # Get the conversation ID from the full URN
                        full_urn = conversation_details.get('entityUrn')
                        conversation_id = self.extract_conversation_id(full_urn) if full_urn else None
                        
                        if conversation_id:
                            # Apply rate limiting before getting full conversation
                            self.rate_limiter.wait()
                            # Get full conversation using the parsed conversation ID
                            full_conversation = self.client.get_conversation(conversation_id)
                            if full_conversation:
                                # Save full conversation
                                self.save_json_output(
                                    full_conversation,
                                    f"conversations/conversation_full_{profile_urn}"
                                )
                                
                                # Create and save simplified version from the full conversation
                                simplified = self.simplify_conversation(full_conversation)
                                self.save_json_output(
                                    simplified,
                                    f"conversations/conversation_simplified_{profile_urn}"
                                )
                                
                                results.append(full_conversation)
                        else:
                            logger.error(f"Could not extract conversation ID from URN for profile {profile_urn}")
                except Exception as e:
                    logger.error(f"Failed to scrape conversation with URN {profile_urn}: {str(e)}")
                    continue
            return results
        except Exception as e:
            logger.error(f"Failed to scrape specific conversations: {str(e)}\n{traceback.format_exc()}")
            return []

    def run(self, action: str = None, profile_ids: List[str] = None,
            profile_id: str = None, profile_urn: str = None, 
            profile_urns: List[str] = None, keywords: str = None,
            profile_data: List[dict] = None, **kwargs):
        """
        Run the LinkedIn scraping job
        
        Args:
            action: Type of data to scrape ('profile', 'profiles', 'connections', 
                   'conversations', 'specific_conversations', 'search')
            profile_ids: List of LinkedIn profile IDs for bulk operations
            profile_id: Single LinkedIn profile ID (for backwards compatibility)
            profile_urn: Single LinkedIn profile URN
            profile_urns: List of LinkedIn profile URNs
            keywords: Search terms when using 'search' action
            profile_data: List of dicts containing profile_id and/or profile_urn for each profile
        """
        try:
            if not action:
                # Default behavior: scrape my connections and conversations
                logger.info("No action specified. Scraping personal connections and conversations...")
                self.scrape_conversations()
                self.scrape_connections()
                return

            # Handle profile_id backward compatibility
            if profile_id and not profile_ids and not profile_data:
                profile_ids = [profile_id]
            
            # Handle single profile_urn
            if profile_urn and not profile_urns and not profile_data:
                profile_urns = [profile_urn]

            if action == "profile" or action == "profiles":
                self.scrape_profiles(
                    profile_ids=profile_ids,
                    profile_urns=profile_urns,
                    profile_data=profile_data
                )
            elif action == "connections":
                self.scrape_connections(
                    profile_urn=profile_urn or MY_PROFILE_URN,
                    profile_id=profile_ids[0] if profile_ids else MY_PROFILE_ID
                )
            elif action == "conversations":
                self.scrape_conversations()
            elif action == "specific_conversations":
                if not profile_urns and not profile_data:
                    logger.error("specific_conversations action requires profile_urns parameter or profile_data")
                    self.print_usage()
                    return
                self.scrape_specific_conversations(
                    profile_urns=profile_urns,
                    profile_data=profile_data
                )
            elif action == "search":
                if not keywords:
                    logger.error("Search action requires keywords parameter")
                    self.print_usage()
                    return
                self.scrape_search_connections(keywords)
            else:
                logger.error(f"Invalid action '{action}' or missing required parameters")
                self.print_usage()
        except Exception as e:
            logger.error(f"Failed to run LinkedIn scraper: {str(e)}\n{traceback.format_exc()}")
    
    def print_usage(self):
        """Print usage instructions"""
        print("""
LinkedIn Scraper Usage:
----------------------
1. Scrape your conversations and connections (default):
   python -m scripts.run linkedin_scraper

2. Scrape one or multiple profiles:
   python -m scripts.run linkedin_scraper --action profiles --profile-ids id1 id2 id3
   python -m scripts.run linkedin_scraper --action profiles --profile-ids-file ids.csv
   python -m scripts.run linkedin_scraper --action profiles --profile-ids ids.csv
   python -m scripts.run linkedin_scraper --action profile --profile-id id1  # backward compatible

3. Scrape connections (defaults to your connections):
   python -m scripts.run linkedin_scraper --action connections [--profile-urn <urn> --profile-id <id>]

4. Scrape all conversations:
   python -m scripts.run linkedin_scraper --action conversations

5. Scrape specific conversations:
   python -m scripts.run linkedin_scraper --action specific_conversations --profile-urns urn1 urn2 urn3
   python -m scripts.run linkedin_scraper --action specific_conversations --profile-urns-file urns.csv
   python -m scripts.run linkedin_scraper --action specific_conversations --profile-urns urns.csv

6. Search within your connections:
   python -m scripts.run linkedin_scraper --action search --keywords "search terms"

Note: For list arguments (profile-ids, profile-urns), you can either:
- Provide values directly on the command line
- Provide a path to a CSV file using the -file suffix argument
- Provide a path to a CSV file as the only value in the list argument
CSV files should contain one item per row in the first column.
""")

if __name__ == "__main__":
    # Example usage
    scraper = LinkedInScraper()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="LinkedIn data scraper")
    parser.add_argument("--action", 
                       choices=["profile", "profiles", "connections", 
                               "conversations", "specific_conversations", "search"],
                       help="Type of data to scrape")
    parser.add_argument("--profile-ids", nargs="+", help="List of LinkedIn profile IDs")
    parser.add_argument("--profile-id", help="Single LinkedIn profile ID (backward compatibility)")
    parser.add_argument("--profile-urn", help="LinkedIn profile URN (defaults to your profile)")
    parser.add_argument("--profile-urns", nargs="+", help="List of LinkedIn profile URNs for conversation scraping")
    parser.add_argument("--keywords", help="Search terms for connection search")
    
    args = parser.parse_args()
    scraper.run(
        action=args.action,
        profile_ids=args.profile_ids,
        profile_id=args.profile_id,
        profile_urn=args.profile_urn,
        profile_urns=args.profile_urns,
        keywords=args.keywords
    ) 