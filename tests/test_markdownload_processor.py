import unittest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from processors.notes.markdownload import MarkdownloadProcessor

class TestMarkdownloadProcessor(unittest.TestCase):
    def setUp(self):
        self.input_dir = Path("/fake/input")
        self.output_dir = Path("/fake/output")
        self.template_path = Path("/fake/template.md")
        
        # Create processor instance
        self.processor = MarkdownloadProcessor(
            self.input_dir,
            self.output_dir,
            self.template_path
        )
        
        # Mock AI model
        self.processor.ai_model = Mock()

    def test_init(self):
        """Test initialization of MarkdownloadProcessor."""
        self.assertEqual(self.processor.input_dir, self.input_dir)
        self.assertEqual(self.processor.output_dir, self.output_dir)
        self.assertEqual(self.processor.template_path, self.template_path)
        self.assertEqual(len(self.processor.files_in_process), 0)

    def test_should_process(self):
        """Test file eligibility checking."""
        # Should process new markdownload files
        self.assertTrue(self.processor.should_process("markdownload_test.md"))
        
        # Should not process non-markdownload files
        self.assertFalse(self.processor.should_process("regular_note.md"))
        self.assertFalse(self.processor.should_process("markdownload_test.txt"))
        
        # Should not process if output exists
        with patch.object(Path, 'exists') as mock_exists:
            mock_exists.return_value = True
            self.assertFalse(self.processor.should_process("markdownload_test.md"))

    @patch('aiofiles.open', new_callable=AsyncMock)
    async def test_process_file_no_frontmatter(self, mock_aiofiles):
        """Test processing file without frontmatter."""
        # Setup test data
        filename = "markdownload_test.md"
        test_content = "This is test content"
        test_summary = "This is a summary"
        test_template = "Template content\n{{title}}\nurl: \nmarkdownload:"
        
        # Mock file operations
        mock_file_handle = AsyncMock()
        mock_file_handle.read = AsyncMock(side_effect=[test_content, test_template])
        mock_file_handle.write = AsyncMock()
        mock_aiofiles.return_value.__aenter__.return_value = mock_file_handle
        
        # Mock AI response
        self.processor.ai_model.message.return_value = test_summary
        
        # Process the file
        await self.processor.process_file(filename)
        
        # Verify AI was called with correct prompt
        self.processor.ai_model.message.assert_called_once_with(
            self.processor.prompt_summary + test_content
        )
        
        # Verify files were read and written
        self.assertEqual(mock_aiofiles.call_count, 3)  # Input, template, and output files

    @patch('aiofiles.open', new_callable=AsyncMock)
    async def test_process_file_with_frontmatter(self, mock_aiofiles):
        """Test processing file with frontmatter."""
        # Setup test data
        filename = "markdownload_test.md"
        test_content = """---
url: https://example.com
---
This is test content"""
        test_summary = "This is a summary"
        test_template = "Template content\n{{title}}\nurl: \nmarkdownload:"
        
        # Mock file operations
        mock_file_handle = AsyncMock()
        mock_file_handle.read = AsyncMock(side_effect=[test_content, test_template])
        mock_file_handle.write = AsyncMock()
        mock_aiofiles.return_value.__aenter__.return_value = mock_file_handle
        
        # Mock AI response
        self.processor.ai_model.message.return_value = test_summary
        
        # Process the file
        await self.processor.process_file(filename)
        
        # Verify template replacements
        mock_file_handle.write.assert_called_once()
        written_content = mock_file_handle.write.call_args[0][0]
        self.assertIn("url: https://example.com", written_content)
        self.assertIn("markdownload: [[markdownload_test]]", written_content)
        self.assertIn(test_summary, written_content)

    @patch('aiofiles.open', new_callable=AsyncMock)
    async def test_process_file_error_handling(self, mock_aiofiles):
        """Test error handling during file processing."""
        filename = "markdownload_test.md"
        
        # Mock to raise an error
        mock_aiofiles.side_effect = Exception("Test error")
        
        # Process should handle the error
        with self.assertRaises(Exception):
            await self.processor.process_file(filename)

if __name__ == '__main__':
    unittest.main()