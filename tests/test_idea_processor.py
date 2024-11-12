import unittest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from processors.notes.ideas import IdeaProcessor

class TestIdeaProcessor(unittest.TestCase):
    def setUp(self):
        self.input_dir = Path("/fake/input")
        self.directory_file = Path("/fake/output/ideas_directory.md")
        
        # Create the processor instance
        self.processor = IdeaProcessor(
            self.input_dir,
            self.directory_file
        )
        
        # Mock the AI model
        self.processor.ai_model = Mock()

    def test_init(self):
        """Test initialization of IdeaProcessor."""
        with patch('pathlib.Path.mkdir') as mock_mkdir, \
             patch('pathlib.Path.exists') as mock_exists, \
             patch('pathlib.Path.write_text') as mock_write:
            
            # Test when directory file doesn't exist
            mock_exists.return_value = False
            processor = IdeaProcessor(self.input_dir, self.directory_file)
            
            mock_mkdir.assert_called_once()
            mock_write.assert_called_once()
            self.assertEqual(processor.input_dir, self.input_dir)
            self.assertEqual(processor.directory_file, self.directory_file)

    def test_should_process(self):
        """Test file eligibility checking."""
        with patch('pathlib.Path.read_text') as mock_read:
            mock_read.return_value = "# Ideas Directory\n[[existing-file.md]]"
            
            # Test valid filename not in directory
            self.assertTrue(self.processor.should_process("test - idea - note.md"))
            
            # Test invalid extensions
            self.assertFalse(self.processor.should_process("test - idea - note.txt"))
            self.assertFalse(self.processor.should_process("test - idea - note.doc"))
            
            # Test filenames without idea marker
            self.assertFalse(self.processor.should_process("test-note.md"))
            self.assertFalse(self.processor.should_process("meeting-note.md"))
            
            # Test already processed file
            self.assertFalse(self.processor.should_process("existing-file.md"))

    @patch('aiofiles.open', new_callable=AsyncMock)
    async def test_process_file(self, mock_aiofiles):
        """Test processing of a single file."""
        # Setup test data
        filename = "test - idea - note.md"
        test_content = """---
date: 2024-01-01
tags: [test]
---
This is a test transcript."""
        
        # Mock file operations
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_aiofiles.return_value.__aenter__.return_value = mock_file_handle
        
        # Mock file reading
        self.processor.read_file = AsyncMock(return_value=test_content)
        
        # Mock AI response
        self.processor.ai_model.message.return_value = """### Test Idea
A test idea description."""
        
        # Process the file
        await self.processor.process_file(filename)
        
        # Verify AI was called with correct prompt
        self.processor.ai_model.message.assert_called_once()
        prompt = self.processor.ai_model.message.call_args[0][0]
        self.assertIn("Analyze this transcript", prompt)
        self.assertIn("This is a test transcript.", prompt)
        
        # Verify file was written
        mock_aiofiles.assert_called_once_with(
            self.directory_file, 
            "a", 
            encoding='utf-8'
        )
        
        # Verify content was written
        write_calls = mock_file_handle.write.call_args_list
        self.assertEqual(len(write_calls), 1)
        written_content = write_calls[0][0][0]
        self.assertIn("[[test - idea - note.md]]", written_content)
        self.assertIn("### Test Idea", written_content)

    @patch('aiofiles.open', new_callable=AsyncMock)
    async def test_process_file_no_frontmatter(self, mock_aiofiles):
        """Test processing file without frontmatter."""
        filename = "test - idea - note.md"
        test_content = "This is a test transcript without frontmatter."
        
        self.processor.read_file = AsyncMock(return_value=test_content)
        
        # Process should complete without writing
        await self.processor.process_file(filename)
        
        # Verify no file was written
        mock_aiofiles.assert_not_called()

    async def test_process_all(self):
        """Test processing of multiple files."""
        with patch.object(Path, 'iterdir') as mock_iterdir:
            mock_iterdir.return_value = [
                Path("/fake/input/test1 - idea - note.md"),
                Path("/fake/input/test2 - idea - note.md"),
                Path("/fake/input/regular-note.md")
            ]
            
            # Mock should_process to only process idea files
            self.processor.should_process = Mock(
                side_effect=lambda x: "- idea -" in x
            )
            
            # Mock process_file
            self.processor.process_file = AsyncMock()
            
            # Process all files
            await self.processor.process_all()
            
            # Verify only idea files were processed
            self.assertEqual(self.processor.process_file.call_count, 2)
            
            # Verify files_in_process is empty after completion
            self.assertEqual(len(self.processor.files_in_process), 0)

if __name__ == '__main__':
    unittest.main()