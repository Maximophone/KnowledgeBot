import requests
from config.secrets import CODA_API_KEY
from config import coda_paths
import time

_MAX_RETRIES = 2
_RETRY_DELAY = 30

class CodaClient:
    def __init__(self, api_token):
        self.api_token = api_token
        self.headers = {'Authorization': f'Bearer {api_token}'}
        self.base_url = 'https://coda.io/apis/v1'

    def _make_request(self, method, url, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY, **kwargs):
        """
        Helper method to make requests with retry logic.

        Args:
            method (str): HTTP method (e.g., 'GET', 'POST', 'PUT', 'DELETE').
            url (str): URL for the request.
            max_retries (int, optional): Maximum number of retries. Defaults to 5.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.
            **kwargs: Additional keyword arguments to pass to the request method.

        Returns:
            Response object or raises an exception.
        """
        retries = 0
        while retries < max_retries:
            try:
                response = requests.request(method, url, headers=self.headers, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 409 and retries < max_retries - 1:
                    retries += 1
                    time.sleep(retry_delay)  # Wait before retrying
                else:
                    raise e

    def list_docs(self, is_owner=False, query=None, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        List Coda docs accessible by the user.

        Args:
            is_owner (bool, optional): Show only docs owned by the user. Defaults to False.
            query (str, optional): Search term to filter docs. Defaults to None.
            max_retries (int, optional): Maximum number of retries. Defaults to 5.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.

        Returns:
            list: List of Coda doc objects matching the query.
        """
        params = {'isOwner': is_owner}
        if query:
            params['query'] = query

        url = f'{self.base_url}/docs'
        response = self._make_request('GET', url, params=params, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()['items']

    def list_docs_in_folder(self, folder_id, is_owner=False, query=None, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        List Coda docs in a specific folder.

        Args:
            folder_id (str): ID of the folder.
            is_owner (bool, optional): Show only docs owned by the user. Defaults to False.
            query (str, optional): Search term to filter docs. Defaults to None.
            max_retries (int, optional): Maximum number of retries. Defaults to 5.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.

        Returns:
            list: List of Coda doc objects matching the query and folder.
        """
        params = {'isOwner': is_owner, 'folderId': folder_id}
        if query:
            params['query'] = query

        url = f'{self.base_url}/docs'
        response = self._make_request('GET', url, params=params, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()['items']

    def create_doc(self, title, source_doc=None, timezone=None, folder_id=None, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        Create a new Coda doc.

        Args:
            title (str): Title of the new doc.
            source_doc (str, optional): ID of an existing doc to copy from. Defaults to None.
            timezone (str, optional): Timezone for the new doc. Defaults to None.
            folder_id (str, optional): ID of the folder to create the doc in. Defaults to None.
            max_retries (int, optional): Maximum number of retries. Defaults to 5.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.

        Returns:
            dict: The created Coda doc object.
        """
        url = f'{self.base_url}/docs'
        body = {
            'title': title,
            'sourceDoc': source_doc,
            'timezone': timezone,
            'folderId': folder_id,
        }
        response = self._make_request('POST', url, json=body, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()

    def get_doc(self, doc_id, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        Get metadata for a Coda doc.

        Args:
            doc_id (str): ID of the Coda doc.
            max_retries (int, optional): Maximum number of retries. Defaults to 5.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.

        Returns:
            dict: The doc object with its metadata.
        """
        url = f'{self.base_url}/docs/{doc_id}'
        response = self._make_request('GET', url, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()

    def get_doc_pages(self, doc_id, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        Get all pages in a Coda doc with retry logic.

        Args:
            doc_id (str): ID of the Coda doc.
            max_retries (int, optional): Maximum number of retries. Defaults to 5.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.

        Returns:
            list: List of page objects for the doc.
        """
        url = f'{self.base_url}/docs/{doc_id}/pages'
        response = self._make_request('GET', url, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()['items']

    def get_page_content(self, doc_id, page_id_or_name, output_format='html', max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        Retrieves the content of the specified page.

        Args:
            doc_id (str): ID of the Coda doc.
            page_id_or_name (str): ID or name of the page.
            output_format (str, optional): The desired output format for the page content. Defaults to 'html'.
            max_retries (int, optional): Maximum number of retries for the content export. Defaults to 10.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.

        Returns:
            bytes: The content of the page.
        """
        export_url = f'{self.base_url}/docs/{doc_id}/pages/{page_id_or_name}/export'
        payload = {'outputFormat': output_format}

        # Initiate the content export
        response = requests.post(export_url, headers=self.headers, json=payload)
        response.raise_for_status()
        request_id = response.json()['id']

        retries = 0
        while retries < max_retries:
            # Check the export status
            status_url = f'{self.base_url}/docs/{doc_id}/pages/{page_id_or_name}/export/{request_id}'
            status_response = self._make_request('GET', status_url, max_retries=max_retries, retry_delay=retry_delay)
            #status_response.raise_for_status()
            status = status_response.json()['status']

            if status == 'complete':
                download_url = status_response.json()['downloadLink']

                # Download the page content
                content_response = requests.get(download_url)
                content_response.raise_for_status()

                return content_response.content
            elif status == 'failed':
                raise Exception(f"Content export failed: {status_response.json()['error']}")
            else:
                retries += 1
                time.sleep(retry_delay)

        raise Exception(f"Failed to retrieve page content after {max_retries} retries.")

    def create_page(self, doc_id, name, content, content_format="html", parent_id=None, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        Create a new page in a Coda doc.

        Args:
            doc_id (str): ID of the Coda doc.
            content (str): The content for the new page.
            parent_id (str, optional): ID of the parent page. Defaults to None.
            max_retries (int, optional): Maximum number of retries. Defaults to 5.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.

        Returns:
            dict: The created page object.
        """
        url = f'{self.base_url}/docs/{doc_id}/pages'
        body = {'name': name, 'pageContent': 
                {'type': 'canvas', 'canvasContent': {'format': content_format, 'content': content}}, 
                'parentId': parent_id}
        response = self._make_request('POST', url, json=body, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()

    def delete_page(self, doc_id, page_id, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        Delete a specific page from a Coda doc.

        Args:
            doc_id (str): ID of the Coda doc.
            page_id (str): ID of the page to delete.
            max_retries (int, optional): Maximum number of retries. Defaults to 5.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.

        Returns:
            dict: The response from the API.
        """
        url = f'{self.base_url}/docs/{doc_id}/pages/{page_id}'
        response = self._make_request('DELETE', url, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()

    def update_page_content(self, doc_id, page_id, new_content, content_format="html", insertion_mode="replace", max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        Update the content of an existing page in a Coda doc.

        Args:
            doc_id (str): ID of the Coda doc.
            page_id (str): ID of the page to update.
            new_content (str): The new content for the page.
            insertion_mode (str): can be "append" or "replace".
            max_retries (int, optional): Maximum number of retries. Defaults to 5.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.

        Returns:
            dict: The updated page object.
        """
        url = f'{self.base_url}/docs/{doc_id}/pages/{page_id}'
        body = {'contentUpdate': 
                {'insertionMode': insertion_mode, 'canvasContent': 
                 {'format': content_format, 'content': new_content}}}
        response = self._make_request('PUT', url, json=body, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()

    def delete_doc(self, doc_id, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        Delete a Coda doc.

        Args:
            doc_id (str): ID of the Coda doc to delete.
            max_retries (int, optional): Maximum number of retries. Defaults to 5.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to 2.

        Returns:
            dict: The response from the API.
        """
        url = f'{self.base_url}/docs/{doc_id}'
        response = self._make_request('DELETE', url, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()
    
    def list_tables(self, doc_id, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        List all tables in a Coda doc.

        Args:
            doc_id (str): ID of the Coda doc.
            max_retries (int, optional): Maximum number of retries. Defaults to _MAX_RETRIES.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to _RETRY_DELAY.

        Returns:
            list: List of table objects in the doc.
        """
        url = f'{self.base_url}/docs/{doc_id}/tables'
        response = self._make_request('GET', url, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()['items']

    def get_table(self, doc_id, table_id, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        Get details of a specific table in a Coda doc.

        Args:
            doc_id (str): ID of the Coda doc.
            table_id (str): ID of the table.
            max_retries (int, optional): Maximum number of retries. Defaults to _MAX_RETRIES.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to _RETRY_DELAY.

        Returns:
            dict: The table object with its details.
        """
        url = f'{self.base_url}/docs/{doc_id}/tables/{table_id}'
        response = self._make_request('GET', url, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()

    def list_columns(self, doc_id, table_id, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        List all columns in a specific table.

        Args:
            doc_id (str): ID of the Coda doc.
            table_id (str): ID of the table.
            max_retries (int, optional): Maximum number of retries. Defaults to _MAX_RETRIES.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to _RETRY_DELAY.

        Returns:
            list: List of column objects in the table.
        """
        url = f'{self.base_url}/docs/{doc_id}/tables/{table_id}/columns'
        response = self._make_request('GET', url, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()['items']

    def get_column(self, doc_id, table_id, column_id, max_retries=_MAX_RETRIES, retry_delay=_RETRY_DELAY):
        """
        Get details of a specific column in a table.

        Args:
            doc_id (str): ID of the Coda doc.
            table_id (str): ID of the table.
            column_id (str): ID of the column.
            max_retries (int, optional): Maximum number of retries. Defaults to _MAX_RETRIES.
            retry_delay (int, optional): Delay in seconds between retries. Defaults to _RETRY_DELAY.

        Returns:
            dict: The column object with its details.
        """
        url = f'{self.base_url}/docs/{doc_id}/tables/{table_id}/columns/{column_id}'
        response = self._make_request('GET', url, max_retries=max_retries, retry_delay=retry_delay)
        return response.json()

if __name__ == "__main__":
    coda_client = CodaClient(CODA_API_KEY)
    print(str(coda_client.list_docs_in_folder(coda_paths.FOLDER_CA)).encode('utf-8'))
    print()
    doc = coda_client.create_doc(title="Test Doc")
    doc_id = doc['id']
    retrieved_doc = coda_client.get_doc(doc_id)
    print(retrieved_doc)
    print()
    print(coda_client.get_doc_pages(doc_id))
    coda_client.delete_doc(doc_id)