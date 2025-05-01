import unittest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from processors.notes.gdoc import GDocProcessor

class TestGDocProcessor(unittest.TestCase):
    def setUp(self):
        self.input_dir = Path("/fake/path")
        self.processor = GDocProcessor(self.input_dir)
        # Mock the GoogleDocUtils and AI model
        self.processor.gdu = Mock()
        self.processor.ai_model = Mock()

    def test_should_process(self):
        # Test non-markdown file
        self.assertFalse(self.processor.should_process("test.txt"))

        # Test file without frontmatter
        with patch("builtins.open", unittest.mock.mock_open(read_data="# Just content")):
            self.assertFalse(self.processor.should_process("test.md"))

        # Test synced file
        content = """---
synced: true
url: https://docs.google.com/test
---
# Content
"""
        with patch("builtins.open", unittest.mock.mock_open(read_data=content)):
            self.assertFalse(self.processor.should_process("test.md"))

        # Test unsynced file with URL
        content = """---
synced: false
url: https://docs.google.com/test
---
# Content
"""
        with patch("builtins.open", unittest.mock.mock_open(read_data=content)):
            self.assertTrue(self.processor.should_process("test.md"))

        # Test file without URL
        content = """---
synced: false
---
# Content
"""
        with patch("builtins.open", unittest.mock.mock_open(read_data=content)):
            self.assertFalse(self.processor.should_process("test.md"))

    @patch('aiofiles.open', new_callable=AsyncMock)
    @patch('os.utime')
    async def test_process_file(self, mock_utime, mock_aiofiles):
        # Setup test data
        filename = "test.md"
        initial_content = """---
synced: false
url: https://docs.google.com/test
---
# Original content
"""
        # Mock file read
        mock_file_handle = AsyncMock()
        mock_file_handle.read.return_value = initial_content
        mock_file_handle.write = AsyncMock()
        mock_aiofiles.return_value.__aenter__.return_value = mock_file_handle

        # Mock Google Doc and AI responses
        self.processor.gdu.get_clean_html_document.return_value = "<html>Doc content</html>"
        self.processor.ai_model.message.return_value = "# Processed content"

        # Process the file
        await self.processor.process_file(filename)

        # Verify interactions
        self.processor.gdu.get_clean_html_document.assert_called_once_with("https://docs.google.com/test")
        self.processor.ai_model.message.assert_called_once()
        
        # Verify file was written with updated content
        mock_file_handle.write.assert_called_once()
        written_content = mock_file_handle.write.call_args[0][0]
        self.assertIn("synced: true", written_content)
        self.assertIn("# Processed content", written_content)
        
        # Verify timestamp was updated
        mock_utime.assert_called_once()

    @patch('aiofiles.open', new_callable=AsyncMock)
    async def test_process_file_error_handling(self, mock_aiofiles):
        filename = "test.md"
        
        # Mock file read to raise an error
        mock_aiofiles.side_effect = Exception("Test error")
        
        # Process should not raise but error should be handled by base class
        await self.processor.process_file(filename)
        
        # Verify Google Doc was not processed
        self.processor.gdu.get_clean_html_document.assert_not_called()

if __name__ == '__main__':
    unittest.main()