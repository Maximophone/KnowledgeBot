"""Script to manage LinkedIn messaging campaigns with templating and tracking."""

from scripts.base_script import BaseScript
from pathlib import Path
import json
import csv
import logging
from datetime import datetime, date, time as dt_time
from typing import List, Dict, Optional, NamedTuple
import re
from config.paths import PATHS
from integrations.linkedin_client import get_linkedin_client
from config.secrets import LINKEDIN_EMAIL, LINKEDIN_PASSWORD
import os
import time
import random
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Rate limiting constants
MIN_DELAY_SECONDS = 60  # Minimum delay between messages
MAX_DELAY_SECONDS = 180  # Maximum delay between messages
MAX_MESSAGES_PER_DAY = 200  # Maximum number of messages per day

class MessageEntry(NamedTuple):
    """Represents a parsed message entry from the campaign file."""
    name: str
    urn_id: str
    message: str
    metadata: Dict[str, str]  # Flexible metadata dictionary for all other fields
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
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            name="linkedin_messenger",
            min_delay_seconds=MIN_DELAY_SECONDS,
            max_delay_seconds=MAX_DELAY_SECONDS,
            max_per_day=MAX_MESSAGES_PER_DAY,
            night_mode=True,
            max_backoff_seconds=900,
        )
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return "Manages LinkedIn messaging campaigns with templating and tracking"
    
    def _replace_placeholders(self, template: str, contact: Dict) -> str:
        """Replace placeholders in template with contact information.
        
        Args:
            template: Message template with placeholders
            contact: Dictionary containing contact information with all necessary fields
                    Any field in the contact dict can be used as a placeholder in the format {field_name}
        
        Returns:
            Personalized message with placeholders replaced
        """
        # Create a copy of the template
        message = template
        
        # Replace all placeholders that exist in the contact dict
        for key, value in contact.items():
            placeholder = "{" + key + "}"
            if placeholder in message:
                message = message.replace(placeholder, str(value))
        
        return message
    
    def _generate_markdown_entry(self, contact: Dict, message: str) -> str:
        """Generate a markdown entry for a single contact with XML tags for parsing.
        
        Args:
            contact: Dictionary containing contact information
            message: Personalized message for the contact
        """
        # Build metadata section with all available fields except the message
        metadata_lines = []
        for key, value in contact.items():
            if key != 'message':  # Skip message field if present
                metadata_lines.append(f"**{key}:** {value}")
        
        return f"""
<message_entry>
### {contact['name']}
{chr(10).join(metadata_lines)}

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
            
            # Extract name from header
            name_match = re.search(r'### (.*?)\n', entry_text)
            name = name_match.group(1) if name_match else ''
            
            # Extract all metadata fields
            metadata = {}
            metadata_matches = re.finditer(r'\*\*(.*?):\*\* (.*?)\n', entry_text)
            for match in metadata_matches:
                key = match.group(1).lower()  # normalize keys to lowercase
                value = match.group(2)
                metadata[key] = value
            
            # Extract message
            message_match = re.search(r'```\n(.*?)\n```', entry_text, re.DOTALL)
            message = message_match.group(1) if message_match else ''
            
            # Check checkboxes
            approved = '- [x] approve_sending' in entry_text
            sent = '- [x] sent' in entry_text
            
            # Get required fields
            urn_id = metadata.pop('urn_id', '')
            
            # Validate required fields
            if not all([name, urn_id]):
                logger.error(f"Entry missing required fields: name and/or urn_id")
                continue
            
            entries.append(MessageEntry(
                name=name,
                urn_id=urn_id,
                message=message,
                metadata=metadata,
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
                        if not self.rate_limiter.wait():
                            logger.error(
                                f"Daily limit of {self.rate_limiter.max_per_day} operations reached for {self.rate_limiter.name}. "
                                f"Please try again tomorrow."
                            )
                            return

                        logger.info(f"Sending message to {entry.name} ({entry.urn_id})")
                        
                        # Send message using profile URN
                        result = self.client.send_message(
                            message_body=entry.message,
                            recipients=[entry.urn_id]
                        )
                        
                        if not result:  # LinkedIn client returns False on success
                            logger.info(f"Successfully sent message to {entry.name}")
                            self.rate_limiter.record_success()
                            # Update file immediately after successful send
                            self._update_campaign_file(campaign_file, entry)
                        else:
                            logger.error(
                                f"Failed to send message to {entry.name}. "
                                f"LinkedIn API returned unexpected response: {result}"
                            )
                            self.rate_limiter.record_failure()
                            
                    except Exception as e:
                        logger.error(
                            f"Error sending message to {entry.name} ({entry.urn_id}). "
                            f"Exception type: {type(e).__name__}. "
                            f"Error details: {str(e)}"
                        )
                        self.rate_limiter.record_failure()
                        continue
                        
        except Exception as e:
            logger.error(
                f"Failed to process campaign file: {campaign_file}. "
                f"Exception type: {type(e).__name__}. "
                f"Error details: {str(e)}"
            )
            raise

    def prepare_messages(self, template_file: str, contacts_file: str) -> Path:
        """Prepare personalized messages for each contact and save to markdown.
        
        Args:
            template_file: Path to the message template file
            contacts_file: Path to the CSV or JSON file containing contacts
                The file must contain at minimum the following fields:
                - name: Full name of the contact
                - first_name: First name of the contact
                - urn_id: LinkedIn URN identifier
        
        Returns:
            Path to the generated markdown file
        """
        try:
            # Read template
            with open(template_file, 'r', encoding='utf-8') as f:
                template = f.read().strip()
            
            # Read contacts based on file extension
            file_extension = Path(contacts_file).suffix.lower()
            contacts = []
            
            if file_extension == '.json':
                with open(contacts_file, 'r', encoding='utf-8') as f:
                    contacts = json.load(f)
            elif file_extension == '.csv':
                with open(contacts_file, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    contacts = list(reader)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}. Please use CSV or JSON files.")
            
            # Validate required fields
            required_fields = ['name', 'first_name', 'urn_id']
            for contact in contacts:
                missing_fields = [field for field in required_fields if not contact.get(field)]
                if missing_fields:
                    raise ValueError(
                        f"Contact is missing required fields: {', '.join(missing_fields)}. "
                        f"Each contact must have: {', '.join(required_fields)}"
                    )
            
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