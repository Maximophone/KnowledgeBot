import os
import unittest
import coda_integration
from config import secrets
from config import coda_paths

class TestCodaClient(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.coda_client = coda_integration.CodaClient(secrets.CODA_API_KEY)
        cls.test_doc = cls.coda_client.create_doc('Test Doc')
        cls.doc_id = cls.test_doc['id']
        cls.coda_client.get_doc(cls.doc_id)
        cls.page_content = '# This is a new page.'
        cls.test_page = cls.coda_client.create_page(cls.doc_id, "Test Page", cls.page_content, content_format = "markdown")
        cls.page_id = cls.test_page['id']

    @classmethod
    def tearDownClass(cls):
        cls.coda_client.delete_page(cls.doc_id, cls.page_id)
        cls.coda_client.delete_doc(cls.doc_id)

    def test_list_docs_in_folder(self):
        # Act
        docs = self.coda_client.list_docs_in_folder(coda_paths.FOLDER_CA)

        # Assert
        self.assertIsInstance(docs, list)
        self.assertTrue(len(docs) > 0)

    def test_get_doc(self):
        # Act
        retrieved_doc = self.coda_client.get_doc(self.doc_id)

        # Assert
        self.assertIsInstance(retrieved_doc, dict)
        self.assertEqual(retrieved_doc['id'], self.doc_id)

    def test_get_doc_pages(self):
        # Act
        pages = self.coda_client.get_doc_pages(self.doc_id)

        # Assert
        self.assertIsInstance(pages, list)

    def test_update_page_content(self):
        # Arrange
        updated_content = 'This is the updated content.'

        # Act
        updated_page = self.coda_client.update_page_content(self.doc_id, self.page_id, updated_content)

        # Assert
        self.assertIsInstance(updated_page, dict)

    def test_get_page_content(self):
        # Act
        retrieved_content = self.coda_client.get_page_content(self.doc_id, self.page_id, output_format="markdown")

        # Assert
        self.assertIsInstance(retrieved_content, bytes)
        self.assertEqual(retrieved_content.decode('utf-8'), self.page_content)


if __name__ == '__main__':
    unittest.main()