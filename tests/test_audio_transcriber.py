import unittest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from datetime import datetime
from processors.audio.transcriber import AudioTranscriber

class TestAudioTranscriber(unittest.TestCase):
    def setUp(self):
        self.input_dir = Path("/fake/input")
        self.output_dir = Path("/fake/output")
        self.processed_dir = Path("/fake/processed")
        self.api_key = "fake_key"
        
        # Create the transcriber instance
        self.transcriber = AudioTranscriber(
            self.input_dir,
            self.output_dir,
            self.processed_dir,
            self.api_key
        )
        
        # Mock the AI models and AssemblyAI
        self.transcriber.ai_model = Mock()
        self.transcriber.transcriber = Mock()

    def test_init(self):
        """Test initialization of AudioTranscriber."""
        self.assertEqual(self.transcriber.input_dir, self.input_dir)
        self.assertEqual(self.transcriber.output_dir, self.output_dir)
        self.assertEqual(self.transcriber.processed_dir, self.processed_dir)
        self.assertEqual(len(self.transcriber.files_in_process), 0)

    def test_classify_transcription(self):
        """Test classification of transcription text."""
        test_text = "This is a test transcription"
        self.transcriber.ai_model.message.return_value = "meeting"
        
        result = self.transcriber.classify_transcription(test_text)
        
        self.assertEqual(result, "meeting")
        self.transcriber.ai_model.message.assert_called_once()
        
    def test_generate_title(self):
        """Test title generation from transcription text."""
        test_text = "This is a test transcription"
        self.transcriber.ai_model.message.return_value = "Test Meeting Title"
        
        result = self.transcriber.generate_title(test_text)
        
        self.assertEqual(result, "Test Meeting Title")
        self.transcriber.ai_model.message.assert_called_once()

    @patch('processors.audio.transcriber.get_recording_date')
    @patch('aiofiles.open', new_callable=AsyncMock)
    @patch('pathlib.Path.rename')
    async def test_process_single_file(self, mock_rename, mock_aiofiles, mock_get_date):
        """Test processing of a single audio file."""
        # Setup test data
        filename = "test_audio.m4a"
        mock_get_date.return_value = datetime(2024, 1, 1)
        
        # Mock file operations
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_aiofiles.return_value.__aenter__.return_value = mock_file_handle
        
        # Mock transcription response
        mock_transcript = Mock()
        mock_transcript.text = "This is a test transcription"
        mock_transcript.json_response = {"fake": "response"}
        mock_transcript.utterances = [
            Mock(speaker="A", text="Hello"),
            Mock(speaker="B", text="World")
        ]
        self.transcriber.transcriber.transcribe.return_value = mock_transcript
        
        # Mock AI responses
        self.transcriber.classify_transcription = Mock(return_value="meeting")
        self.transcriber.generate_title = Mock(return_value="Test Meeting")
        
        # Process the file
        self.transcriber.files_in_process.add(filename)
        await self.transcriber.process_single_file(filename)
        
        # Verify transcription was requested
        self.transcriber.transcriber.transcribe.assert_called_once()
        
        # Verify files were written
        self.assertEqual(mock_aiofiles.call_count, 2)  # JSON and MD files
        
        # Verify file was moved to processed directory
        mock_rename.assert_called_once()
        
        # Verify file was removed from processing set
        self.assertNotIn(filename, self.transcriber.files_in_process)

    @patch('processors.audio.transcriber.get_recording_date')
    @patch('aiofiles.open', new_callable=AsyncMock)
    async def test_process_single_file_error_handling(self, mock_aiofiles, mock_get_date):
        """Test error handling during file processing."""
        filename = "test_audio.m4a"
        
        # Mock to raise an error
        mock_get_date.side_effect = Exception("Test error")
        
        # Process should handle the error
        self.transcriber.files_in_process.add(filename)
        with self.assertRaises(Exception):
            await self.transcriber.process_single_file(filename)
        
        # Verify file was removed from processing set even after error
        self.assertNotIn(filename, self.transcriber.files_in_process)

    @patch('asyncio.create_task')
    async def test_process_all(self, mock_create_task):
        """Test processing of multiple files."""
        # Mock directory contents
        with patch.object(Path, 'iterdir') as mock_iterdir:
            mock_iterdir.return_value = [
                Path("/fake/input/file1.m4a"),
                Path("/fake/input/file2.m4a")
            ]
            
            # Process all files
            await self.transcriber.process_all()
            
            # Verify tasks were created for each file
            self.assertEqual(mock_create_task.call_count, 2)

if __name__ == '__main__':
    unittest.main()