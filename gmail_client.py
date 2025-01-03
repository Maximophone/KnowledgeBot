# gmail_client.py

import os
import pickle
import base64

from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
import quopri

def simplify_gmail_message(message):
    """
    Process a Gmail API message to simplify its content structure.
    Keeps all original fields but adds a 'simplified_content' field with plain text content.
    """
    def decode_content(part):
        """Helper function to decode message content"""
        if 'data' not in part.get('body', {}):
            return ''
        
        # Get the content data
        data = part['body']['data']
        
        # Decode base64
        decoded_bytes = base64.urlsafe_b64decode(data)
        
        # Handle different content transfer encodings
        if 'headers' in part:
            for header in part['headers']:
                if header['name'].lower() == 'content-transfer-encoding':
                    if header['value'].lower() == 'quoted-printable':
                        decoded_bytes = quopri.decodestring(decoded_bytes)
                    break
        
        # Try to decode as UTF-8, fallback to ISO-8859-1 if needed
        try:
            return decoded_bytes.decode('utf-8')
        except UnicodeDecodeError:
            return decoded_bytes.decode('iso-8859-1')

    def extract_plain_text(payload):
        """Extract plain text content from payload"""
        if payload.get('mimeType') == 'text/plain':
            return decode_content(payload)
        
        if payload.get('mimeType') == 'multipart/alternative':
            parts = payload.get('parts', [])
            # Look for text/plain part first
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    return decode_content(part)
            # Fallback to first part if no text/plain
            if parts:
                return decode_content(parts[0])
        
        return ''

    # Create a copy of the original message
    processed_message = message.copy()
    
    # Add simplified content while keeping original payload
    if 'payload' in message:
        processed_message['simplified_content'] = extract_plain_text(message['payload'])
    
    return processed_message

class GmailClient:
    def __init__(self,
                 credentials_path='credentials.json',
                 token_path='token.pickle',
                 scopes=None):
        """
        :param credentials_path: Path to your downloaded OAuth credentials JSON file.
        :param token_path: Path to store the OAuth token (pickle).
        :param scopes: List of Gmail API scopes you need.
        """
        # By default, we use full mail scope; replace with narrower scopes if desired
        self.scopes = scopes or ['https://mail.google.com/']
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None

        # Try loading existing token
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token_file:
                creds = pickle.load(token_file)

        # If no valid credentials, prompt user login
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.scopes
                )
                creds = flow.run_local_server(port=0)

            # Save new token for future runs
            with open(self.token_path, 'wb') as token_file:
                pickle.dump(creds, token_file)

        return build('gmail', 'v1', credentials=creds)

    def send_email(self, to, subject, body):
        """
        Send a plain-text email.
        :param to: Recipient email address
        :param subject: Email subject
        :param body: Plain-text message content
        :return: API response dict containing message ID, etc.
        """
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_body = {'raw': raw_message}

        sent_message = self.service.users().messages().send(
            userId='me', 
            body=send_body
        ).execute()
        return sent_message

    def list_emails(self, query='', label_ids=None, max_results=10):
        """
        List emails in your mailbox.
        :param query: Search query (e.g. 'is:unread', 'subject:Hello')
        :param label_ids: List of label IDs (e.g. ['INBOX'])
        :param max_results: How many messages to return
        :return: List of messages (each is a dict with at least an 'id')
        """
        if label_ids is None:
            label_ids = []

        response = self.service.users().messages().list(
            userId='me',
            q=query,
            labelIds=label_ids,
            maxResults=max_results
        ).execute()

        # If no messages are found, the 'messages' key may not exist
        return response.get('messages', [])

    def get_email(self, message_id):
        """
        Retrieve a full email by ID (with headers, body, etc.).
        :param message_id: The ID of the message to retrieve
        :return: A dict with detailed message data
        """
        message = self.service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        return message
    
    def search_emails(
    self,
    sender=None,
    subject=None,
    is_unread=False,
    has_attachment=False,
    from_date=None,
    to_date=None,
    label_ids=None,
    max_results=10
    ):
        """
        Search emails based on multiple optional parameters.

        :param sender: Filter by sender email address (e.g. 'someone@example.com')
        :param subject: Filter by subject keyword/phrase (e.g. 'Meeting')
        :param is_unread: If True, only show unread messages (adds 'is:unread')
        :param has_attachment: If True, only show messages that have attachments
        :param from_date: Limit results to messages after this date (format: 'YYYY/MM/DD')
        :param to_date: Limit results to messages before this date (format: 'YYYY/MM/DD')
        :param label_ids: List of label IDs to filter by (e.g. ['INBOX', 'Label_123'])
        :param max_results: Maximum number of messages to retrieve
        :return: A list of message dicts, each containing 'id' and 'threadId'
        """
        # Build query string from the provided parameters
        conditions = []

        if sender:
            conditions.append(f"from:{sender}")
        if subject:
            conditions.append(f"subject:{subject}")
        if is_unread:
            conditions.append("is:unread")
        if has_attachment:
            conditions.append("has:attachment")
        if from_date:
            # Gmail uses after:YYYY/MM/DD (messages after this date)
            conditions.append(f"after:{from_date}")
        if to_date:
            # Gmail uses before:YYYY/MM/DD (messages before this date)
            conditions.append(f"before:{to_date}")

        query_str = " ".join(conditions)

        if label_ids is None:
            label_ids = []

        response = self.service.users().messages().list(
            userId='me',
            q=query_str,
            labelIds=label_ids,
            maxResults=max_results
        ).execute()

        return response.get('messages', [])


if __name__ == '__main__':
    # Example usage
    client = GmailClient()

    # Send an email
    response = client.send_email(
        to='fournes.maxime@gmail.com',
        subject='Hello from Python!',
        body='This is a test email.'
    )
    print("Email sent:", response)

    # List some emails
    emails = client.list_emails(query='is:unread', max_results=5)
    print("Emails found:", emails)

    # Fetch first email if there is one
    if emails:
        msg_id = emails[0]['id']
        full_msg = client.get_email(msg_id)
        print("Fetched email details:", full_msg)
