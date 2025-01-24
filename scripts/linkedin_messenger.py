"""Script to manage LinkedIn messaging campaigns with templating and tracking."""

from scripts.base_script import BaseScript
from pathlib import Path
import json
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, NamedTuple
import re
from config.paths import PATHS
from integrations.linkedin_client import get_linkedin_client
from config.secrets import LINKEDIN_EMAIL, LINKEDIN_PASSWORD
import os
import time
import random

logger = logging.getLogger(__name__)

# Rate limiting constants
MIN_DELAY_SECONDS = 15  # Minimum delay between messages
MAX_DELAY_SECONDS = 30  # Maximum delay between messages
MAX_MESSAGES_PER_DAY = 200  # Maximum number of messages per day

class MessageEntry(NamedTuple):
    """Represents a parsed message entry from the campaign file."""
    name: str
    job_title: str
    location: str
    urn: str
    message: str
    approved: bool
    sent: bool
    raw_text: str  # Original text block for replacement

class LinkedInMessenger(BaseScript):
    def __init__(self):
        self._name = "linkedin_messenger"
        super().__init__()
        
        # Create messages directory if it doesn't exist
        PATHS.linkedin_messages.mkdir(parents=True, exist_ok=True)
        
        # Initialize LinkedIn client
        self.client = get_linkedin_client(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
        
        # Initialize rate limiting from persistent storage
        self._init_rate_limiting()
    
    def _init_rate_limiting(self):
        """Initialize rate limiting data from persistent storage."""
        self.rate_limit_file = PATHS.linkedin_messages / "rate_limit_data.json"
        
        # Default rate limit data
        self.rate_limit_data = {
            "date": str(date.today()),
            "messages_sent": 0,
            "last_message_time": None
        }
        
        # Load existing data if available
        if self.rate_limit_file.exists():
            try:
                with open(self.rate_limit_file, 'r') as f:
                    stored_data = json.load(f)
                
                # Reset counter if it's a new day
                if stored_data["date"] == str(date.today()):
                    self.rate_limit_data = stored_data
                else:
                    # It's a new day, save default data
                    self._save_rate_limit_data()
            except Exception as e:
                logger.error(f"Error loading rate limit data: {e}")
                # Use default data and save it
                self._save_rate_limit_data()
        else:
            # No existing data, save default data
            self._save_rate_limit_data()
    
    def _save_rate_limit_data(self):
        """Save rate limiting data to persistent storage."""
        try:
            with open(self.rate_limit_file, 'w') as f:
                json.dump(self.rate_limit_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving rate limit data: {e}")
    
    def _wait_for_rate_limit(self):
        """Implement rate limiting logic between messages."""
        current_time = time.time()
        
        # Check if we've hit the daily limit
        if self.rate_limit_data["messages_sent"] >= MAX_MESSAGES_PER_DAY:
            raise Exception(f"Daily limit of {MAX_MESSAGES_PER_DAY} messages reached. Please try again tomorrow.")
        
        # If this isn't the first message, ensure minimum delay
        if self.rate_limit_data["last_message_time"] is not None:
            time_since_last = current_time - self.rate_limit_data["last_message_time"]
            if time_since_last < MIN_DELAY_SECONDS:
                # Calculate required wait time
                wait_time = MIN_DELAY_SECONDS - time_since_last
                # Add some random jitter
                jitter = random.uniform(0, MAX_DELAY_SECONDS - MIN_DELAY_SECONDS)
                total_wait = wait_time + jitter
                
                logger.info(f"Rate limiting: waiting {total_wait:.1f} seconds before next message...")
                time.sleep(total_wait)
        
        # Update rate limit data
        self.rate_limit_data["last_message_time"] = current_time
        self.rate_limit_data["messages_sent"] += 1
        self._save_rate_limit_data()
        
        logger.info(f"Messages sent today: {self.rate_limit_data['messages_sent']}/{MAX_MESSAGES_PER_DAY}")
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return "Manages LinkedIn messaging campaigns with templating and tracking"
    
    def _replace_placeholders(self, template: str, contact: Dict) -> str:
        """Replace placeholders in template with contact information."""
        # Get first name by splitting full name
        first_name = contact['name'].split()[0]
        
        # Replace placeholders
        message = template.replace("{first_name}", first_name)
        
        return message
    
    def _generate_markdown_entry(self, contact: Dict, message: str) -> str:
        """Generate a markdown entry for a single contact with XML tags for parsing."""
        return f"""
<message_entry>
### {contact['name']}
**Job Title:** {contact.get('jobtitle', 'N/A')}
**Location:** {contact.get('location', 'N/A')}
**URN:** {contact['urn_id']}

**Message:**
```
{message}
```

- [ ] approve_sending
- [ ] sent
</message_entry>
"""

    def _parse_campaign_file(self, campaign_file: Path) -> List[MessageEntry]:
        """Parse the campaign markdown file and extract message entries.
        
        Args:
            campaign_file: Path to the campaign markdown file
            
        Returns:
            List of MessageEntry objects
        """
        with open(campaign_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract message entries using XML tags
        entries = []
        message_blocks = re.finditer(r'<message_entry>\n(.*?)\n</message_entry>', 
                                   content, re.DOTALL)
        
        for block in message_blocks:
            raw_text = block.group(0)
            entry_text = block.group(1)
            
            # Extract name
            name_match = re.search(r'### (.*?)\n', entry_text)
            name = name_match.group(1) if name_match else ''
            
            # Extract job title
            job_match = re.search(r'\*\*Job Title:\*\* (.*?)\n', entry_text)
            job_title = job_match.group(1) if job_match else 'N/A'
            
            # Extract location
            location_match = re.search(r'\*\*Location:\*\* (.*?)\n', entry_text)
            location = location_match.group(1) if location_match else 'N/A'
            
            # Extract URN
            urn_match = re.search(r'\*\*URN:\*\* (.*?)\n', entry_text)
            urn = urn_match.group(1) if urn_match else ''
            
            # Extract message
            message_match = re.search(r'```\n(.*?)\n```', entry_text, re.DOTALL)
            message = message_match.group(1) if message_match else ''
            
            # Check checkboxes
            approved = '- [x] approve_sending' in entry_text
            sent = '- [x] sent' in entry_text
            
            entries.append(MessageEntry(
                name=name,
                job_title=job_title,
                location=location,
                urn=urn,
                message=message,
                approved=approved,
                sent=sent,
                raw_text=raw_text
            ))
        
        return entries

    def _update_campaign_file(self, campaign_file: Path, entry: MessageEntry) -> None:
        """Update a single entry in the campaign file to mark it as sent.
        
        Args:
            campaign_file: Path to the campaign markdown file
            entry: The MessageEntry to update
        """
        with open(campaign_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create updated entry text
        updated_text = entry.raw_text.replace('- [ ] sent', '- [x] sent')
        
        # Replace in content
        updated_content = content.replace(entry.raw_text, updated_text)
        
        # Write back to file
        with open(campaign_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        os.utime(campaign_file, None) # necessary to trigger Obsidian to reload the file

    def send_messages(self, campaign_file: Path) -> None:
        """Send approved messages and update their status.
        
        Args:
            campaign_file: Path to the campaign markdown file
        """
        try:
            entries = self._parse_campaign_file(campaign_file)
            
            # Count how many messages we need to send
            to_send = sum(1 for entry in entries if entry.approved and not entry.sent)
            if to_send > MAX_MESSAGES_PER_DAY:
                logger.warning(
                    f"Warning: {to_send} messages to send exceeds daily limit of {MAX_MESSAGES_PER_DAY}. "
                    f"Only the first {MAX_MESSAGES_PER_DAY} will be sent."
                )
            
            for entry in entries:
                if entry.approved and not entry.sent:
                    try:
                        # Apply rate limiting
                        self._wait_for_rate_limit()
                        
                        logger.info(f"Sending message to {entry.name} ({entry.urn})")
                        
                        # Send message using profile URN
                        result = self.client.send_message(
                            message_body=entry.message,
                            recipients=[entry.urn]
                        )
                        
                        if not result:  # LinkedIn client returns False on success
                            logger.info(f"Successfully sent message to {entry.name}")
                            # Update file immediately after successful send
                            self._update_campaign_file(campaign_file, entry)
                        else:
                            logger.error(f"Failed to send message to {entry.name}")
                            
                    except Exception as e:
                        logger.error(f"Error sending message to {entry.name}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"Failed to process campaign file: {str(e)}")
            raise

    def prepare_messages(self, template_file: str, contacts_file: str) -> Path:
        """Prepare personalized messages for each contact and save to markdown.
        
        Args:
            template_file: Path to the message template file
            contacts_file: Path to the JSON file containing journalist contacts
        
        Returns:
            Path to the generated markdown file
        """
        try:
            # Read template
            with open(template_file, 'r', encoding='utf-8') as f:
                template = f.read().strip()
            
            # Read contacts
            with open(contacts_file, 'r', encoding='utf-8') as f:
                contacts = json.load(f)
            
            # Generate markdown content
            markdown_content = "# LinkedIn Message Campaign\n"
            markdown_content += f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            
            # Add template for reference
            markdown_content += "## Message Template\n"
            markdown_content += f"```\n{template}\n```\n\n"
            markdown_content += "## Messages\n"
            
            # Generate entry for each contact
            for contact in contacts:
                personalized_message = self._replace_placeholders(template, contact)
                markdown_content += self._generate_markdown_entry(contact, personalized_message)
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = PATHS.linkedin_messages / f"linkedin_campaign_{timestamp}.md"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info(f"Generated message campaign file: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to prepare messages: {str(e)}")
            raise
    
    def run(self, action: str = None, template_file: str = None, 
            contacts_file: str = None, campaign_file: str = None, **kwargs):
        """Run the LinkedIn messaging workflow
        
        Args:
            action: Type of action ('prepare' or 'send')
            template_file: Path to message template file (for 'prepare' action)
            contacts_file: Path to JSON file with contacts (for 'prepare' action)
            campaign_file: Path to campaign markdown file (for 'send' action)
        """
        if not action:
            logger.error("No action specified")
            self.print_usage()
            return
            
        if action == "prepare":
            if not template_file or not contacts_file:
                logger.error("Template file and contacts file required for prepare action")
                self.print_usage()
                return
            self.prepare_messages(template_file, contacts_file)
            
        elif action == "send":
            if not campaign_file:
                logger.error("Campaign file required for send action")
                self.print_usage()
                return
            self.send_messages(PATHS.linkedin_messages / campaign_file)
            
        else:
            logger.error(f"Invalid action: {action}")
            self.print_usage()
    
    def print_usage(self):
        """Print usage instructions"""
        print("""
LinkedIn Messenger Usage:
------------------------
1. Prepare messages from template:
   python -m scripts.run linkedin_messenger --action prepare --template-file path/to/template.txt --contacts-file path/to/contacts.json

2. Send approved messages:
   python -m scripts.run linkedin_messenger --action send --campaign-file path/to/campaign.md
""")

if __name__ == "__main__":
    import argparse
    
    messenger = LinkedInMessenger()
    
    parser = argparse.ArgumentParser(description="LinkedIn messaging campaign manager")
    parser.add_argument("--action", choices=["prepare", "send"],
                       help="Action to perform")
    parser.add_argument("--template-file", help="Path to message template file")
    parser.add_argument("--contacts-file", help="Path to contacts JSON file")
    parser.add_argument("--campaign-file", help="Path to campaign markdown file")
    
    args = parser.parse_args()
    messenger.run(
        action=args.action,
        template_file=args.template_file,
        contacts_file=args.contacts_file,
        campaign_file=args.campaign_file
    ) 