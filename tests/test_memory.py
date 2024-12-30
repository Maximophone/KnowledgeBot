import unittest
from unittest.mock import patch, Mock, mock_open
from pathlib import Path
import json
from ai.toolsets.memory import patch_memory, validate_filepath
from config.paths import PATHS

class TestPatchMemory(unittest.TestCase):
    def setUp(self):
        # Create a mock for PATHS.ai_memory
        self.mock_memory_path = Path("fake/ai_memory").resolve()
        PATHS.ai_memory = self.mock_memory_path

    def test_invalid_filepath(self):
        """Test handling of invalid filepaths"""
        invalid_paths = [
            "../test.md",  # Contains ..
            "/test.md",    # Starts with /
            "\\test.md",   # Starts with \
            "",           # Empty string
            "test/../../escape.md",  # Path traversal attempt
            "CON.md",     # Windows reserved name
            ".hidden.md"  # Hidden file
        ]
        
        for path in invalid_paths:
            with self.assertRaises(ValueError):
                patch_memory(path, "some diff content")

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.resolve')
    def test_nonexistent_file(self, mock_resolve, mock_exists):
        """Test attempting to patch a non-existent file"""
        mock_exists.return_value = False
        mock_resolve.return_value = self.mock_memory_path / "test.md"
        
        result = patch_memory("test.md", "some diff content")
        self.assertEqual(result, "Error: File test.md does not exist")

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.resolve')
    @patch('builtins.open')
    @patch('patch_ng.fromstring')
    def test_successful_patch(self, mock_fromstring, mock_open, mock_resolve, mock_exists):
        """Test successful application of a patch"""
        # Mock file existence and path resolution
        mock_exists.return_value = True
        mock_resolve.return_value = self.mock_memory_path / "test.md"
        
        # Mock patch_ng's PatchSet
        mock_patchset = Mock()
        mock_patchset.apply.return_value = True
        mock_fromstring.return_value = mock_patchset
        
        # Create a simple diff
        diff_content = """--- a/test.md
+++ b/test.md
@@ -1 +1 @@
-original content
+modified content"""
        
        result = patch_memory("test.md", diff_content)
        
        # Verify the result
        self.assertEqual(result, "Successfully applied patch to test.md")
        
        # Verify patch was created and applied
        mock_fromstring.assert_called_once_with(diff_content)
        mock_patchset.apply.assert_called_once_with(strip=0, root=str(self.mock_memory_path))

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.resolve')
    @patch('patch_ng.fromstring')
    def test_patch_error_handling(self, mock_fromstring, mock_resolve, mock_exists):
        """Test handling of patch application errors"""
        # Mock file existence and path resolution
        mock_exists.return_value = True
        mock_resolve.return_value = self.mock_memory_path / "test.md"
        
        # Mock patch_ng raising an error
        mock_fromstring.side_effect = Exception("Invalid patch format")
        
        # Create an invalid diff
        invalid_diff = """--- a/test.md
+++ b/test.md
@@ invalid diff format"""
        
        result = patch_memory("test.md", invalid_diff)
        self.assertTrue(result.startswith("Error applying patch:"))

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.resolve')
    def test_path_traversal_prevention(self, mock_resolve, mock_exists):
        """Test prevention of path traversal attempts"""
        mock_exists.return_value = True
        mock_resolve.return_value = Path("fake/unauthorized.md").resolve()
        
        with self.assertRaises(ValueError) as context:
            patch_memory("../unauthorized.md", "some diff")
        
        self.assertIn("Invalid filepath", str(context.exception))

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.resolve')
    @patch('patch_ng.fromstring')
    def test_encoding_handling(self, mock_fromstring, mock_resolve, mock_exists):
        """Test handling of UTF-8 encoded content"""
        # Mock file existence and path resolution
        mock_exists.return_value = True
        mock_resolve.return_value = self.mock_memory_path / "test.md"
        
        # Mock patch_ng's PatchSet
        mock_patchset = Mock()
        mock_patchset.apply.return_value = True
        mock_fromstring.return_value = mock_patchset
        
        # Create a diff with UTF-8 characters
        diff_content = """--- a/test.md
+++ b/test.md
@@ -1 +1 @@
-Original content with UTF-8 characters: 测试, José
+Modified content with UTF-8 characters: 新内容, María"""
        
        result = patch_memory("test.md", diff_content)
        self.assertEqual(result, "Successfully applied patch to test.md")
        
        # Verify patch was created and applied with correct encoding
        mock_fromstring.assert_called_once_with(diff_content)
        mock_patchset.apply.assert_called_once_with(strip=0, root=str(self.mock_memory_path))