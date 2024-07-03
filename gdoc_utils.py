# gdoc_utils.py

import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import io
from googleapiclient.http import MediaIoBaseDownload
from bs4 import BeautifulSoup
import re

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

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
                    self.credentials_path, SCOPES)
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

    def get_document_as_html(self, doc_id_or_url):
        if 'docs.google.com' in doc_id_or_url:
            doc_id = self.extract_doc_id_from_url(doc_id_or_url)
        else:
            doc_id = doc_id_or_url

        creds = self.get_credentials()
        service = build('drive', 'v3', credentials=creds)

        try:
            request = service.files().export_media(fileId=doc_id, mimeType='text/html')
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print(f"Download {int(status.progress() * 100)}%.")

            content = fh.getvalue().decode('utf-8')
            return content

        except Exception as error:
            print(f'An error occurred: {error}')
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

    def get_clean_document(self, doc_id_or_url):
        html_content = self.get_document_as_html(doc_id_or_url)
        if html_content:
            return self.remove_styles(html_content)
        return None

def main():
    # Usage example
    gdoc_utils = GoogleDocUtils()
    FILE_ID = '1kB8SSmauWQSqxMmdG04ubpOtw-rTN3h8P36rncubuwc'
    clean_html = gdoc_utils.get_clean_document(FILE_ID)
    
    if clean_html:
        print("Clean HTML Content:")
        print(clean_html[:1000])  # Print first 1000 characters
        
        # Save the clean HTML content to a file
        with open('clean_document.html', 'w', encoding='utf-8') as f:
            f.write(clean_html)
        print("Clean HTML content saved to 'clean_document.html'")

if __name__ == '__main__':
    main()