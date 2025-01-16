import requests
from config.secrets import CODA_API_KEY
from config.coda_paths import FOLDER_PERSO, FOLDER_CONTACTS, DOC_RELATIONS, DOC_TEST_TABLES
import time
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class CodaTablesClient:
    def __init__(self, api_token, base_url="https://coda.io/apis/v1"):
        self.api_token = api_token
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    def list_tables(self, doc_id, limit=25, page_token=None, sort_by=None, table_types=None):
        """
        Returns a list of tables in a Coda doc.

        Args:
            doc_id (str): ID of the doc.
            limit (int, optional): Maximum number of results to return. Defaults to 25.
            page_token (str, optional): Pagination token. Defaults to None.
            sort_by (str, optional): Sort order (e.g., 'natural', 'createdAt'). Defaults to None.
            table_types (list, optional): List of table types to include (e.g., ['table', 'view']). Defaults to None.

        Returns:
            dict: List of tables.
        """
        url = f"{self.base_url}/docs/{doc_id}/tables"
        params = {
            "limit": limit,
            "pageToken": page_token,
            "sortBy": sort_by,
            "tableTypes": table_types,
        }
        params = {k: v for k, v in params.items() if v is not None}
        if table_types and isinstance(table_types, list):
            params["tableTypes"] = ",".join(table_types)
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_table(self, doc_id, table_id_or_name, use_updated_table_layouts=None):
        """
        Returns details about a specific table or view.

        Args:
            doc_id (str): ID of the doc.
            table_id_or_name (str): ID or name of the table.
            use_updated_table_layouts (bool, optional): Whether to return "detail" and "form" for the `layout` field of detail and form layouts respectively.

        Returns:
            dict: Table details.
        """
        url = f"{self.base_url}/docs/{doc_id}/tables/{table_id_or_name}"
        params = {}
        if use_updated_table_layouts is not None:
            params["useUpdatedTableLayouts"] = use_updated_table_layouts
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def list_rows(self, doc_id, table_id_or_name, query=None, sort_by=None, use_column_names=False, value_format="simple", visible_only=None, limit=25, page_token=None, sync_token=None):
        """
        Returns a list of rows in a table.

        Args:
            doc_id (str): ID of the doc.
            table_id_or_name (str): ID or name of the table.
            query (str, optional): Query used to filter rows. Defaults to None.
            sort_by (str, optional): Sort order (e.g., 'createdAt', 'natural'). Defaults to None.
            use_column_names (bool, optional): Use column names in output instead of IDs. Defaults to False.
            value_format (str, optional): Format of cell values ('simple', 'simpleWithArrays', 'rich'). Defaults to "simple".
            visible_only (bool, optional): If true, returns only visible rows and columns. Defaults to None.
            limit (int, optional): Maximum number of results to return. Defaults to 25.
            page_token (str, optional): Pagination token. Defaults to None.
            sync_token (str, optional): Sync token for retrieving new results. Defaults to None.

        Returns:
            dict: List of rows.
        """
        url = f"{self.base_url}/docs/{doc_id}/tables/{table_id_or_name}/rows"
        params = {
            "query": query,
            "sortBy": sort_by,
            "useColumnNames": use_column_names,
            "valueFormat": value_format,
            "visibleOnly": visible_only,
            "limit": limit,
            "pageToken": page_token,
            "syncToken": sync_token,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def upsert_rows(self, doc_id, table_id_or_name, rows_data, disable_parsing=None):
        """
        Inserts or updates rows in a table.

        Args:
            doc_id (str): ID of the doc.
            table_id_or_name (str): ID or name of the table.
            rows_data (list): List of rows to insert or update.
            disable_parsing (bool, optional): If true, the API will not attempt to parse the data in any way. Defaults to None.

        Returns:
            dict: Result of the upsert operation.
        """
        url = f"{self.base_url}/docs/{doc_id}/tables/{table_id_or_name}/rows"
        payload = {
            "rows": rows_data
        }
        params = {}
        if disable_parsing is not None:
            params["disableParsing"] = disable_parsing

        response = requests.post(url, headers=self.headers, json=payload, params=params)
        if response.status_code == 202:
            return response.json()
        else:
            response.raise_for_status()

    def delete_rows(self, doc_id, table_id_or_name, row_ids):
        """
        Deletes rows from a table.

        Args:
            doc_id (str): ID of the doc.
            table_id_or_name (str): ID or name of the table.
            row_ids (list): List of row IDs to delete.

        Returns:
            dict: Result of the delete operation.
        """
        url = f"{self.base_url}/docs/{doc_id}/tables/{table_id_or_name}/rows"
        payload = {
            "rowIds": row_ids
        }
        response = requests.delete(url, headers=self.headers, json=payload)
        if response.status_code == 202:
            return response.json()
        else:
            response.raise_for_status()

    def get_row(self, doc_id, table_id_or_name, row_id_or_name, use_column_names=False, value_format="simple"):
        """
        Returns details about a specific row.

        Args:
            doc_id (str): ID of the doc.
            table_id_or_name (str): ID or name of the table.
            row_id_or_name (str): ID or name of the row.
            use_column_names (bool, optional): Use column names in output instead of IDs. Defaults to False.
            value_format (str, optional): Format of cell values ('simple', 'simpleWithArrays', 'rich'). Defaults to "simple".

        Returns:
            dict: Row details.
        """
        url = f"{self.base_url}/docs/{doc_id}/tables/{table_id_or_name}/rows/{row_id_or_name}"
        params = {
            "useColumnNames": use_column_names,
            "valueFormat": value_format,
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def update_row(self, doc_id, table_id_or_name, row_id_or_name, row_data, disable_parsing=None):
        """
        Updates a specific row.

        Args:
            doc_id (str): ID of the doc.
            table_id_or_name (str): ID or name of the table.
            row_id_or_name (str): ID or name of the row.
            row_data (dict): Data to update the row with.
            disable_parsing (bool, optional): If true, the API will not attempt to parse the data in any way. Defaults to None.

        Returns:
            dict: Result of the update operation.
        """
        url = f"{self.base_url}/docs/{doc_id}/tables/{table_id_or_name}/rows/{row_id_or_name}"
        payload = {
            "row": row_data
        }
        params = {}
        if disable_parsing is not None:
            params["disableParsing"] = disable_parsing

        response = requests.put(url, headers=self.headers, json=payload, params=params)

        if response.status_code == 202:
            return response.json()
        else:
            response.raise_for_status()


    def delete_row(self, doc_id, table_id_or_name, row_id_or_name):
        """
        Deletes a specific row.

        Args:
            doc_id (str): ID of the doc.
            table_id_or_name (str): ID or name of the table.
            row_id_or_name (str): ID or name of the row.

        Returns:
            dict: Result of the delete operation.
        """
        url = f"{self.base_url}/docs/{doc_id}/tables/{table_id_or_name}/rows/{row_id_or_name}"
        response = requests.delete(url, headers=self.headers)
        if response.status_code == 202:
            return response.json()
        else:
            response.raise_for_status()

    def push_button(self, doc_id, table_id_or_name, row_id_or_name, column_id_or_name):
        """
        Pushes a button in a specific row and column.

        Args:
            doc_id (str): ID of the doc.
            table_id_or_name (str): ID or name of the table.
            row_id_or_name (str): ID or name of the row.
            column_id_or_name (str): ID or name of the column containing the button.

        Returns:
            dict: Result of the push button operation.
        """
        url = f"{self.base_url}/docs/{doc_id}/tables/{table_id_or_name}/rows/{row_id_or_name}/buttons/{column_id_or_name}"
        response = requests.post(url, headers=self.headers)
        if response.status_code == 202:
            return response.json()
        else:
            response.raise_for_status()

    def list_columns(self, doc_id, table_id_or_name, limit=25, page_token=None, visible_only=None):
        """
        Returns a list of columns in a table.

        Args:
            doc_id (str): ID of the doc.
            table_id_or_name (str): ID or name of the table.
            limit (int, optional): Maximum number of results to return. Defaults to 25.
            page_token (str, optional): Pagination token. Defaults to None.
            visible_only (bool, optional): If true, returns only visible columns for the table. Defaults to None.

        Returns:
            dict: List of columns.
        """
        url = f"{self.base_url}/docs/{doc_id}/tables/{table_id_or_name}/columns"
        params = {
            "limit": limit,
            "pageToken": page_token,
            "visibleOnly": visible_only,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    client = CodaTablesClient(api_token=CODA_API_KEY)
    tables = client.list_tables(doc_id=DOC_TEST_TABLES)
    # print(tables)

    rows = client.list_rows(doc_id=DOC_TEST_TABLES, table_id_or_name="Table")
    print(rows)

    new_row = {"cells": [{"column": "Name", "value": "Value 1"}, {"column": "Column 2", "value": "Value 2"}]}
    upsert_result = client.upsert_rows(doc_id=DOC_TEST_TABLES, table_id_or_name="Table", rows_data=[new_row])
    print(upsert_result)

    added_row_id = upsert_result["addedRowIds"][0]

    time.sleep(1)
    row = client.get_row(doc_id=DOC_TEST_TABLES, table_id_or_name="Table", row_id_or_name="Value 1")
    print(row)

    time.sleep(1)

    client.delete_row(doc_id=DOC_TEST_TABLES, table_id_or_name="Table", row_id_or_name="Value 1")

# Example Usage:
# coda_client = CodaTablesClient(api_token="YOUR_API_TOKEN")
# tables = coda_client.list_tables(doc_id="YOUR_DOC_ID")
# print(tables)

# rows = coda_client.list_rows(doc_id="YOUR_DOC_ID", table_id_or_name="YOUR_TABLE_ID")
# print(rows)

# new_row = {"cells": [{"column": "column-id-1", "value": "Value 1"}, {"column": "column-id-2", "value": "Value 2"}]}
# upsert_result = coda_client.upsert_rows(doc_id="YOUR_DOC_ID", table_id_or_name="YOUR_TABLE_ID", rows_data=[new_row])
# print(upsert_result)

# row = coda_client.get_row(doc_id="YOUR_DOC_ID", table_id_or_name="YOUR_TABLE_ID", row_id_or_name="YOUR_ROW_ID")
# print(row)