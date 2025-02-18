"""Script for sending bulk emails using templates and CSV data."""

from scripts.base_script import BaseScript
import csv
import re
from string import Formatter
from typing import Dict, List, Tuple
from integrations.gmail_client import GmailClient
from config.logging_config import setup_logger
from datetime import datetime
from utils.rate_limiter import RateLimiter

logger = setup_logger(__name__)

def is_valid_email(email: str) -> bool:
    """Validate email address format."""
    # Basic email validation regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

class BulkEmailSender(BaseScript):
    def __init__(self):
        self._name = "bulk_email_sender"
        super().__init__()
        self.gmail_client = GmailClient()
        
        # Initialize rate limiter with email-specific settings
        self.rate_limiter = RateLimiter(
            name="gmail_sender",
            min_delay_seconds=18,
            max_delay_seconds=22, 
            max_per_day=1500  # Gmail's limit is around 500, we're being conservative
        )
        
        # Default sender name
        self.from_name = "Maxime Fournes"
        
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return "Send bulk emails using a template with placeholders and CSV data"
    
    def parse_template(self, template_path: str) -> Tuple[str, str]:
        """Parse the email template file to extract subject and body.
        
        Template format:
        SUBJECT:
        Your subject line here
        BODY:
        Your email body here
        
        Returns:
            Tuple of (subject, body)
        """
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split into sections
        sections = content.split('BODY:', 1)
        if len(sections) != 2 or 'SUBJECT:' not in sections[0]:
            raise ValueError("Template must contain 'SUBJECT:' and 'BODY:' sections")
        
        # Extract subject and body
        subject = sections[0].replace('SUBJECT:', '').strip()
        body = sections[1].strip()
        
        return subject, body
    
    def get_template_placeholders(self, template: str) -> set:
        """Extract all placeholders from the template using string.Formatter"""
        return {
            field_name
            for _, field_name, _, _ in Formatter().parse(template)
            if field_name is not None
        }
    
    def validate_template_against_csv(self, placeholders: set, csv_headers: List[str]) -> None:
        """Validate that all template placeholders exist in CSV headers"""
        missing_fields = placeholders - set(csv_headers)
        if missing_fields:
            raise ValueError(
                f"Template placeholders {missing_fields} not found in CSV headers: {csv_headers}"
            )
    
    def read_csv_data(self, csv_path: str) -> Tuple[List[str], List[Dict[str, str]]]:
        """Read CSV file and return headers and data rows.
        When multiple email addresses are present (separated by |), only the first one is used."""
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                if not headers or 'email' not in headers:
                    raise ValueError("CSV must have headers with 'email' column")
                
                # Process rows and take first email if multiple exist
                data = []
                skipped = []
                for row in reader:
                    # Skip empty rows
                    if not row['email'].strip():
                        continue
                    
                    # Take first email if multiple exist
                    email = row['email'].split('|')[0].strip()
                    
                    # Validate email
                    if not is_valid_email(email):
                        skipped.append((email, "Invalid email format"))
                        continue
                    
                    row['email'] = email
                    data.append(row)
                
                # Log skipped entries
                if skipped:
                    logger.warning(f"Skipped {len(skipped)} invalid entries:")
                    for email, reason in skipped:
                        logger.warning(f"  - {email}: {reason}")
            
            return headers, data
            
        except Exception as e:
            logger.error(f"Error reading CSV file: {str(e)}")
            raise
    
    def send_templated_email(self, template_subject: str, template_body: str, 
                           row_data: Dict[str, str]) -> Tuple[bool, str]:
        """Send a single email using template and row data.
        
        Returns:
            Tuple of (success: bool, error_message: str)
        """
        try:
            # Replace placeholders in subject and body
            subject = template_subject.format(**row_data)
            body = template_body.format(**row_data)
            
            # Convert newlines to <br> tags for HTML
            body = body.replace('\n', '<br>')
            
            # Send email
            self.gmail_client.send_email(
                to=row_data['email'],
                subject=subject,
                body=body,
                from_name=self.from_name
            )
            self.rate_limiter.record_success()
            return True, None
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to send email to {row_data['email']}: {error_msg}")
            self.rate_limiter.record_failure()
            return False, error_msg
    
    def run(self, template_file: str = None, csv_file: str = None, from_name: str = None, **kwargs):
        """Run the bulk email sender.
        
        Args:
            template_file: Path to email template file
            csv_file: Path to CSV file with email addresses and data
            from_name: Display name for the sender (optional)
        """
        if not template_file or not csv_file:
            logger.error("Both template_file and csv_file are required")
            self.print_usage()
            return
            
        # Override default from_name if provided
        if from_name:
            self.from_name = from_name
        
        try:
            # Parse template
            template_subject, template_body = self.parse_template(template_file)
            
            # Get all placeholders from template
            subject_placeholders = self.get_template_placeholders(template_subject)
            body_placeholders = self.get_template_placeholders(template_body)
            all_placeholders = subject_placeholders | body_placeholders
            
            # Read CSV data
            headers, data = self.read_csv_data(csv_file)
            
            # Validate template against CSV headers
            self.validate_template_against_csv(all_placeholders, headers)
            
            # Track detailed results
            results = {
                'timestamp': datetime.now().isoformat(),
                'template_file': template_file,
                'csv_file': csv_file,
                'total_recipients': len(data),
                'successful_count': 0,
                'failed_count': 0,
                'recipients': []
            }
            
            # Process each row
            for row in data:
                # Apply rate limiting
                if not self.rate_limiter.wait():
                    logger.error("Daily email sending limit reached")
                    break
                
                # Send email and get result
                success, error_msg = self.send_templated_email(template_subject, template_body, row)
                
                # Track detailed recipient result, only including used placeholders
                recipient_result = {
                    'email': row['email'],
                    'success': success,
                    'timestamp': datetime.now().isoformat(),
                }
                
                # Only include data that was used in the template
                used_data = {
                    k: row[k] for k in all_placeholders
                    if k in row  # Ensure the field exists in the row
                }
                if used_data:  # Only add data if there were placeholders
                    recipient_result['data'] = used_data
                
                if success:
                    results['successful_count'] += 1
                else:
                    results['failed_count'] += 1
                    recipient_result['error'] = error_msg
                
                results['recipients'].append(recipient_result)
            
            # Save detailed results
            self.save_json_output(results, 'bulk_email_results')
            
            # Log summary
            logger.info("Bulk email sending completed:")
            logger.info(f"Total recipients: {results['total_recipients']}")
            logger.info(f"Successful: {results['successful_count']}")
            logger.info(f"Failed: {results['failed_count']}")
            if results['failed_count'] > 0:
                failed_emails = [r['email'] for r in results['recipients'] if not r['success']]
                logger.info(f"Failed recipients: {failed_emails}")
                
        except Exception as e:
            logger.error(f"Failed to process bulk email sending: {str(e)}")
            raise
    
    def print_usage(self):
        """Print usage instructions"""
        print("""
Bulk Email Sender Usage:
------------------------
python -m scripts.run bulk_email_sender --template-file path/to/template.txt --csv-file path/to/data.csv

Template format:
---------------
SUBJECT:
Your subject line with {placeholders}
BODY:
Your email body with {placeholders}

CSV format:
-----------
email,field1,field2,...
address@example.com,value1,value2,...
""")

if __name__ == "__main__":
    sender = BulkEmailSender()
    sender.print_usage() 