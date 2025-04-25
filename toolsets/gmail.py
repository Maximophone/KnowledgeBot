from ai_core.tools import tool
from integrations.gmail_client import GmailClient, filter_email_data, process_gmail_message
import json

# Initialize client
gmail_client = GmailClient()

@tool(
    description="Send an email through Gmail. This tool allows sending plain text emails to specified recipients. "
                "It handles the email composition and sending process through the authenticated Gmail account. "
                "The email can be sent from any authorized address including Google Groups. "
                "Multiple recipients and CC addresses can be specified using comma-separated values.",
    to="The recipient's email address(es), comma-separated for multiple recipients",
    cc="Optional CC recipient(s), comma-separated for multiple CC addresses",
    subject="The subject line of the email",
    body="The html content of the email message (make sure to use <br> for line breaks)",
    from_name="Optional display name for the sender",
    from_email="Optional sender email address (must have permission to send as this address)",
    safe=False
)
def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str = None,
    from_name: str = None,
    from_email: str = None
) -> str:
    """Sends an email through Gmail"""
    # Split recipients by comma and strip whitespace
    to_list = [email.strip() for email in to.split(',') if email.strip()]
    cc_list = [email.strip() for email in cc.split(',')] if cc else None
    
    result = gmail_client.send_email(
        to=to_list,
        subject=subject,
        body=body,
        cc=cc_list,
        from_name=from_name,
        from_email=from_email
    )
    return json.dumps(result)

@tool(
    description="Search for emails in Gmail using various filters. This tool provides a powerful way to search through "
                "your Gmail inbox using multiple criteria. You can combine different search parameters to narrow down "
                "results. The search is performed on the authenticated Gmail account. Results are limited to prevent "
                "overwhelming responses.",
    sender="Optional email address to filter messages from a specific sender",
    subject="Optional keyword or phrase to filter messages by subject",
    is_unread="If True, only show unread messages",
    has_attachment="If True, only show messages with attachments",
    from_date="Optional date to filter messages after (format: YYYY/MM/DD)",
    to_date="Optional date to filter messages before (format: YYYY/MM/DD)",
    max_results="Maximum number of messages to return (default: 10)",
    safe=True
)
def search_emails(
    sender: str = None,
    subject: str = None,
    is_unread: bool = False,
    has_attachment: bool = False,
    from_date: str = None,
    to_date: str = None,
    max_results: int = 10
) -> str:
    """Searches for emails using various filters"""
    results = gmail_client.search_emails(
        sender=sender,
        subject=subject,
        is_unread=is_unread,
        has_attachment=has_attachment,
        from_date=from_date,
        to_date=to_date,
        max_results=max_results
    )
    return json.dumps(results)

@tool(
    description="Retrieve the full content and details of a specific email message. This tool fetches comprehensive "
                "information about an email including headers, body, and metadata. Use this after finding message IDs "
                "through the search_emails tool to get complete message details.",
    message_id="The unique ID of the email message to retrieve (obtained from search results)",
    simplified="If True, the email content will be decoded and simplified to a single string",
    safe=True
)
def get_email_content(message_id: str, simplified: bool = True) -> str:
    """Gets the full content of a specific email"""
    message = gmail_client.get_email(message_id)
    if simplified:
        message = process_gmail_message(message)
        message = filter_email_data(message)
    return json.dumps(message)

@tool(
    description="List recent emails from your Gmail inbox. This tool provides a simple way to fetch recent messages "
                "with optional filtering by labels and search query. It's useful for getting a quick overview of "
                "recent messages or finding specific messages using Gmail's search syntax.",
    query="Optional Gmail search query (e.g., 'is:unread', 'subject:Hello')",
    label_ids="Optional list of Gmail label IDs to filter by (e.g., ['INBOX'])",
    max_results="Maximum number of messages to return (default: 10)",
    safe=True
)
def list_recent_emails(
    query: str = '',
    label_ids: str = None,
    max_results: int = 10,
) -> str:
    """Lists recent emails with optional filtering"""
    if label_ids:
        label_ids = json.loads(label_ids)
    messages = gmail_client.list_emails(
        query=query,
        label_ids=label_ids,
        max_results=max_results
    )
    return json.dumps(messages)

# Export the tools
TOOLS = [
    send_email,
    search_emails,
    get_email_content,
    list_recent_emails
] 