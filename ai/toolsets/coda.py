from ..tools import tool
from config.secrets import CODA_API_KEY
from coda_integration import CodaClient
from coda_tables import CodaTablesClient
import json

# Initialize clients
coda_client = CodaClient(CODA_API_KEY)
coda_tables_client = CodaTablesClient(CODA_API_KEY)

@tool(
    description="List all folders accessible to the user in Coda",
    safe=True
)
def list_folders() -> str:
    """Lists all folders accessible to the user"""
    docs_owned = coda_client.list_docs(is_owner=True)
    docs_shared = coda_client.list_docs(is_owner=False)
    docs = docs_owned + docs_shared
    folders = set()
    for doc in docs:
        if 'folderId' in doc and doc['folderId']:
            folders.add(doc['folderId'])
    return json.dumps(list(folders))

@tool(
    description="List all documents accessible to the user in Coda, or filter with a query",
    query="Optional query to filter documents (a search term used to filter down results)",
    safe=True
)
def list_docs(query: str = None) -> str:
    """Lists all documents, or filter with a query"""
    docs_owned = coda_client.list_docs(is_owner=True, query=query)
    docs_shared = coda_client.list_docs(is_owner=False, query=query)
    docs = docs_owned + docs_shared
    return json.dumps(docs)

@tool(
    description="List all documents in a specific Coda folder",
    folder_id="The ID of the folder to list documents from",
    safe=True
)
def list_docs_in_folder(folder_id: str) -> str:
    """Lists all documents in a specific folder"""
    docs_owned = coda_client.list_docs_in_folder(is_owner=True,folder_id=folder_id)
    docs_shared = coda_client.list_docs_in_folder(is_owner=False,folder_id=folder_id)
    docs = docs_owned + docs_shared
    return json.dumps(docs)

@tool(
    description="List all pages in a Coda document",
    doc_id="The ID of the document to list pages from",
    safe=True
)
def list_pages(doc_id: str) -> str:
    """Lists all pages in a document"""
    pages = coda_client.get_doc_pages(doc_id)
    return json.dumps(pages)

@tool(
    description="List all tables in a Coda document",
    doc_id="The ID of the document to list tables from",
    safe=True
)
def list_tables(doc_id: str) -> str:
    """Lists all tables in a document"""
    tables = coda_tables_client.list_tables(doc_id)
    return json.dumps(tables)

@tool(
    description="Get the schema (columns and their properties) of a specific table",
    doc_id="The ID of the document containing the table",
    table_id_or_name="The ID or name of the table to get the schema for. ID is more reliable.",
    safe=True
)
def get_table_schema(doc_id: str, table_id_or_name: str) -> str:
    """Gets the schema of a specific table"""
    table = coda_tables_client.get_table(doc_id, table_id_or_name)
    columns = coda_tables_client.list_columns(doc_id, table_id_or_name)
    table['columns'] = columns
    return json.dumps(table)

@tool(
    description="List rows from a specific table with optional filtering and sorting",
    doc_id="The ID of the document containing the table",
    table_id_or_name="The ID or name of the table to get rows from. ID is more reliable.",
    query="Optional query used to filter returned rows, specified as <column_id_or_name>:<value>. Example: query=c-tuVwxYz:\"Apple\". If you'd like to use a column name instead of an ID, you must quote it (e.g., \"My Column\":123). Also note that value is a JSON value; if you'd like to use a string, you must surround it in quotes (e.g., \"groceries\").",
    use_column_names="Whether to receive column names instead of column IDs in the response",
    limit="Maximum number of rows to return. No maximum value. Defaults to 100.",
    safe=True
)
def list_table_rows(
    doc_id: str,
    table_id_or_name: str,
    query: str = None,
    use_column_names: bool = True,
    limit: int = 100
) -> str:
    """Lists rows from a specific table"""
    rows = coda_tables_client.list_rows(
        doc_id,
        table_id_or_name,
        query=query,
        use_column_names=use_column_names,
        limit=limit
    )
    return json.dumps(rows)

@tool(
    description="Insert or update rows in a table. Requires specific JSON format for row data.",
    doc_id="The ID of the document containing the table",
    table_id_or_name="The ID or name of the table to update. ID is more reliable.",
    rows_data="JSON string containing an array of row objects with format: [{\"cells\": [{\"column\": \"c-xxx\", \"value\": \"value\"}]}]. For relation columns, the value can be either a row ID (i-xxx) or the display value/name of the related row. Example: [{\"cells\": [{\"column\": \"c-columnId\", \"value\": \"text\"}, {\"column\": \"c-relationColumnId\", \"value\": \"Related Row Name\"}]}]",
    safe=False
)
def upsert_table_rows(doc_id: str, table_id_or_name: str, rows_data: str) -> str:
    """Inserts or updates rows in a table"""
    rows = json.loads(rows_data)
    result = coda_tables_client.upsert_rows(doc_id, table_id_or_name, rows)
    return json.dumps(result)

@tool(
    description="Delete specific rows from a table",
    doc_id="The ID of the document containing the table",
    table_id_or_name="The ID or name of the table to delete rows from. ID is more reliable.",
    row_ids="JSON string containing an array of row IDs to delete. Example: [\"i-xxx\", \"i-yyy\"]",
    safe=False
)
def delete_table_rows(doc_id: str, table_id_or_name: str, row_ids: str) -> str:
    """Deletes specific rows from a table"""
    ids = json.loads(row_ids)
    result = coda_tables_client.delete_rows(doc_id, table_id_or_name, ids)
    return json.dumps(result)

@tool(
    description="Update a specific row in a table",
    doc_id="The ID of the document containing the table",
    table_id_or_name="The ID or name of the table containing the row. ID is more reliable.",
    row_id_or_name="The ID or name of the row to update. ID is more reliable.",
    row_data="JSON string containing the new values for the row, must follow format: {\"cells\": [{\"column\": \"c-xxx\", \"value\": \"value\"}]}. For relation columns, the value can be either a row ID (i-xxx) or the display value/name of the related row. Example: {\"cells\": [{\"column\": \"c-columnId\", \"value\": \"text\"}, {\"column\": \"c-relationColumnId\", \"value\": \"Related Row Name\"}]}",
    safe=False
)
def update_table_row(
    doc_id: str,
    table_id_or_name: str,
    row_id_or_name: str,
    row_data: str
) -> str:
    """Updates a specific row in a table"""
    data = json.loads(row_data)
    result = coda_tables_client.update_row(
        doc_id,
        table_id_or_name,
        row_id_or_name,
        data
    )
    return json.dumps(result)

@tool(
    description="Get the content of a specific page in a Coda document",
    doc_id="The ID of the document containing the page",
    page_id_or_name="The ID or name of the page to read. ID is more reliable.",
    output_format="The format to return the content in ('html' or 'markdown'). Defaults to 'html'.",
    safe=True
)
def get_page_content(doc_id: str, page_id_or_name: str, output_format: str = 'html') -> str:
    """Gets the content of a specific page"""
    content = coda_client.get_page_content(
        doc_id,
        page_id_or_name,
        output_format=output_format
    )
    return content.decode('utf-8')

# Export the tools
TOOLS = [
    list_folders,
    list_docs,
    list_docs_in_folder,
    list_pages,
    list_tables,
    get_table_schema,
    list_table_rows,
    upsert_table_rows,
    delete_table_rows,
    update_table_row,
    get_page_content
] 