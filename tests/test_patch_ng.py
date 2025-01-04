import unittest
import tempfile
import shutil
import os
from pathlib import Path
from patch_ng import fromstring

class TestPatchNG(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory for our test files"""
        self.original_dir = os.getcwd()  # Save the original directory
        self.test_dir = tempfile.mkdtemp()
        # Change to the test directory for all operations
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up the temporary directory after tests"""
        os.chdir(self.original_dir)  # Change back to original directory
        shutil.rmtree(self.test_dir)

    def test_simple_replacement(self):
        """Test a simple one-line replacement patch"""
        # Create original file with explicit line ending
        with open("test.txt", "w", newline='\n') as f:
            f.write("Original Content\n")

        # Create patch
        diff = """--- a/test.txt
+++ b/test.txt
@@ -1 +1 @@
-Original Content
+New Content
"""
        
        # Apply patch
        patchset = fromstring(diff.encode())
        result = patchset.apply(root=os.getcwd(), strip=1)  # strip=1 to remove 'a/' and 'b/'
        
        # Verify
        self.assertTrue(result)
        with open("test.txt", "r", newline='\n') as f:
            self.assertEqual(f.read(), "New Content\n")

    def test_create_new_file(self):
        """Test creating a new file with a patch"""
        diff = """--- /dev/null
+++ b/newfile.txt
@@ -0,0 +1,3 @@
+Line 1
+Line 2
+Line 3
"""
        
        # Apply patch
        patchset = fromstring(diff.encode())
        result = patchset.apply(root=os.getcwd(), strip=0)
        
        # Verify
        self.assertTrue(result, "Failed to create newfile.txt via patch.")
        self.assertTrue(os.path.exists("newfile.txt"), "newfile.txt not found after patch creation.")
        with open("newfile.txt", "r") as f:
            self.assertEqual(f.read(), "Line 1\nLine 2\nLine 3\n")

    def test_delete_file(self):
        """Test deleting a file with a patch"""
        # Create file to be deleted
        with open("delete.txt", "w", newline='\n') as f:
            f.write("Line 1\nLine 2\nLine 3\n")

        diff = """--- a/delete.txt
+++ /dev/null
@@ -1,3 +0,0 @@
-Line 1
-Line 2
-Line 3
"""
        
        # Apply patch
        patchset = fromstring(diff.encode())
        result = patchset.apply(root=os.getcwd(), strip=1)
        
        # Verify
        self.assertTrue(result, "Failed to apply deletion patch.")
        self.assertFalse(os.path.exists("delete.txt"), "delete.txt still exists after patch deletion.")

    def test_subfolder_patch(self):
        """
        Test patching a file within a subfolder structure.
        Ensures that patch_ng correctly handles nested paths (strip=1, 'a/' and 'b/' prefixes).
        """
        # Create a subfolder and file
        os.makedirs("subfolder", exist_ok=True)
        with open("subfolder/nested.txt", "w", newline='\n') as f:
            f.write("Nested Original Line\n")

        diff = """--- a/subfolder/nested.txt
+++ b/subfolder/nested.txt
@@ -1 +1 @@
-Nested Original Line
+Replaced Nested Line
"""

        patchset = fromstring(diff.encode())
        # We set root to the current directory and use strip=1 to remove 'a/' or 'b/'
        result = patchset.apply(root=os.getcwd(), strip=1)

        self.assertTrue(result, "Failed to apply patch in a subfolder.")
        with open("subfolder/nested.txt", "r", newline='\n') as f:
            self.assertEqual(f.read(), "Replaced Nested Line\n")

    def test_create_file_in_subfolder(self):
        """Test creating a new file inside a subfolder via patch."""
        # Make sure subfolder exists
        os.makedirs("subfolder/deep", exist_ok=True)

        diff = """--- /dev/null
+++ subfolder/deep/brand_new.txt
@@ -0,0 +1,2 @@
+Hello from subfolder
+This file did not exist before
"""

        patchset = fromstring(diff.encode())
        result = patchset.apply(root=os.getcwd(), strip=0)

        self.assertTrue(result, "Failed to create a new file in the subfolder.")
        new_file_path = Path("subfolder/deep/brand_new.txt")
        self.assertTrue(new_file_path.exists(), f"{new_file_path} was not created by the patch.")
        with new_file_path.open("r") as f:
            content = f.read()
            self.assertEqual(content, "Hello from subfolder\nThis file did not exist before\n")

    def test_modify_and_delete_in_subfolder(self):
        """Test patch that modifies one file and deletes another within a subfolder."""
        # Setup subfolder and files
        os.makedirs("subfolder/twofiles", exist_ok=True)
        with open("subfolder/twofiles/keepme.txt", "w", newline='\n') as f:
            f.write("Keep me line\n")
        with open("subfolder/twofiles/deleteme.txt", "w", newline='\n') as f:
            f.write("Delete me line\n")

        diff = """--- subfolder/twofiles/keepme.txt
+++ subfolder/twofiles/keepme.txt
@@ -1 +1 @@
-Keep me line
+I have been modified

--- subfolder/twofiles/deleteme.txt
+++ /dev/null
@@ -1 +0,0 @@
-Delete me line
"""

        patchset = fromstring(diff.encode())
        result = patchset.apply(root=os.getcwd(), strip=0)

        self.assertTrue(result, "Failed to apply multi-file patch in subfolder.")

        # Verify modifications
        with open("subfolder/twofiles/keepme.txt", "r", newline='\n') as f:
            self.assertEqual(f.read(), "I have been modified\n")

        # Verify deletion
        self.assertFalse(
            os.path.exists("subfolder/twofiles/deleteme.txt"),
            "Expected deleteme.txt to be removed by patch, but it still exists."
        )


if __name__ == "__main__":
    unittest.main() 