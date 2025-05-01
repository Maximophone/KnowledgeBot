# gdoc_utils.py

import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import io
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from bs4 import BeautifulSoup
import re
from config.logging_config import setup_logger
import traceback
from config.services_config import GOOGLE_SCOPES

logger = setup_logger(__name__)

class GoogleDocUtils:
    def __init__(self, credentials_path='credentials.json'):
        self.credentials_path = credentials_path
        self.creds = None

    def get_credentials(self):
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                self.creds = pickle.load(token)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, GOOGLE_SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(self.creds, token)
        return self.creds

    @staticmethod
    def extract_doc_id_from_url(url):
        # Pattern to match Google Docs URLs
        patterns = [
            r'/document/d/([a-zA-Z0-9-_]+)',  # Standard URL
            r'/document/u/\d+/d/([a-zA-Z0-9-_]+)',  # URL with user number
            r'docs.google.com/.*[?&]id=([a-zA-Z0-9-_]+)'  # Old style URL
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        raise ValueError("Invalid Google Docs URL")

    @staticmethod
    def extract_folder_id_from_url(url):
        # Pattern to match Google Drive folder URLs
        patterns = [
            r'/folders/([a-zA-Z0-9-_]+)',  # Standard folder URL
            r'/drive/u/\d+/folders/([a-zA-Z0-9-_]+)' # Folder URL with user number
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        raise ValueError("Invalid Google Drive folder URL")

    def get_document_as_markdown(self, doc_id_or_url) -> str | None:
        return self.get_document(doc_id_or_url, mime_type='text/markdown')

    def get_document_as_html(self, doc_id_or_url) -> str | None:
        return self.get_document(doc_id_or_url, mime_type='text/html')
    
    def get_document(self, doc_id_or_url, mime_type='text/markdown') -> str | None:
        if 'docs.google.com' in doc_id_or_url:
            doc_id = self.extract_doc_id_from_url(doc_id_or_url)
        else:
            doc_id = doc_id_or_url

        creds = self.get_credentials()
        service = build('drive', 'v3', credentials=creds)

        try:
            request = service.files().export_media(fileId=doc_id, mimeType=mime_type)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.info(f"Download {int(status.progress() * 100)}%.")

            content = fh.getvalue().decode('utf-8')
            return content

        except Exception as error:
            logger.error(f'An error occurred: {error}')
            logger.error(traceback.format_exc())
            return None

    @staticmethod
    def remove_styles(html_content):
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove all style attributes
        for tag in soup.find_all(True):
            if 'style' in tag.attrs:
                del tag['style']

        # Remove all <style> tags
        for style in soup.find_all('style'):
            style.decompose()

        # # Remove all class attributes
        # for tag in soup.find_all(True):
        #     if 'class' in tag.attrs:
        #         del tag['class']

        return str(soup)

    def get_clean_html_document(self, doc_id_or_url):
        html_content = self.get_document_as_html(doc_id_or_url)
        if html_content:
            return self.remove_styles(html_content)
        return None

    def create_document_from_text(self, title: str, text_content: str, folder_id: str, mime_type: str = 'text/plain') -> str | None:
        """Creates a new Google Doc with the given title and text content in the specified folder."""
        creds = self.get_credentials()
        service = build('drive', 'v3', credentials=creds)

        try:
            # Prepare file metadata
            file_metadata = {
                'name': title,
                'mimeType': 'application/vnd.google-apps.document',
                'parents': [folder_id] # Specify the folder
            }

            # Prepare media content (convert text to bytes)
            media = MediaIoBaseUpload(
                io.BytesIO(text_content.encode('utf-8')),
                mimetype=mime_type, # Upload as plain text, Google converts it
                resumable=True
            )

            # Create the file
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink', # Fields to return
                supportsAllDrives=True  # <-- Explicitly add this for Shared Drive compatibility
            ).execute()

            doc_id = file.get('id')
            doc_link = file.get('webViewLink')
            logger.info(f"Successfully created Google Doc: ID='{doc_id}', Link='{doc_link}'")
            return doc_link

        except Exception as error:
            logger.error(f'An error occurred while creating the document: {error}')
            logger.error(traceback.format_exc())
            return None

    def delete_document(self, file_id: str) -> bool:
        """Deletes a file from Google Drive using its ID."""
        creds = self.get_credentials()
        service = build('drive', 'v3', credentials=creds)

        try:
            service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
            logger.info(f"Successfully deleted Google Drive file with ID: {file_id}")
            return True
        except Exception as error:
            logger.error(f'An error occurred while deleting file {file_id}: {error}')
            logger.error(traceback.format_exc())
            return False

def main():
    """Example usage of GoogleDocUtils."""
    gdoc_utils = GoogleDocUtils()
    FILE_ID = '1kB8SSmauWQSqxMmdG04ubpOtw-rTN3h8P36rncubuwc'
    clean_html = gdoc_utils.get_clean_html_document(FILE_ID)
    
    if clean_html:
        print("Clean HTML Content:")
        print(clean_html[:1000])  # Print first 1000 characters
        
        # Save the clean HTML content to a file
        with open('clean_document.html', 'w', encoding='utf-8') as f:
            f.write(clean_html)
        print("Clean HTML content saved to 'clean_document.html'")

if __name__ == '__main__':
    main()