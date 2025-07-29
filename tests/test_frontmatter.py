"""
These tests cover:
    parse_frontmatter:
    - Valid frontmatter parsing
    - Various invalid cases (no frontmatter, invalid YAML, missing delimiters)
    frontmatter_to_text:
    - Proper YAML formatting
    - Nested structure handling
    - Proper delimiter placement
    update_frontmatter:
    - Updating existing frontmatter
    - Adding new frontmatter to content without any
    - Empty updates
    - Content preservation
    Unicode handling:
    - Proper handling of non-ASCII characters
"""

import unittest
import os
from processors.common.frontmatter import (
    read_text_from_file, parse_frontmatter_from_content, frontmatter_to_text, 
    update_frontmatter_in_content, read_text_from_content,
    has_frontmatter_from_content, has_frontmatter_from_file
)

class TestReadText(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

    def tearDown(self):
        for f in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, f))
        os.rmdir(self.test_dir)

    def _create_file(self, filename, content):
        path = os.path.join(self.test_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_with_valid_frontmatter(self):
        content = "---\ntitle: Test\n---\nHello World"
        path = self._create_file("valid.md", content)
        self.assertEqual(read_text_from_file(path), "Hello World")

    def test_no_frontmatter(self):
        content = "Hello World"
        path = self._create_file("no_fm.md", content)
        self.assertEqual(read_text_from_file(path), content)

    def test_empty_file(self):
        path = self._create_file("empty.md", "")
        self.assertEqual(read_text_from_file(path), "")

    def test_only_frontmatter(self):
        content = "---\ntitle: Test\n---"
        path = self._create_file("only_fm.md", content)
        self.assertEqual(read_text_from_file(path), "")

    def test_frontmatter_with_three_dashes_inside(self):
        content = "---\ntitle: Test\ncontent: ---\n---\nHello World"
        path = self._create_file("dashes_inside.md", content)
        self.assertEqual(read_text_from_file(path), "Hello World")

    def test_malformed_frontmatter_start(self):
        content = " ---\ntitle: Test\n---\nHello World"
        path = self._create_file("malformed_start.md", content)
        self.assertEqual(read_text_from_file(path), content)

    def test_malformed_frontmatter_end(self):
        content = "---\ntitle: Test\n --- \nHello World"
        path = self._create_file("malformed_end.md", content)
        self.assertEqual(read_text_from_file(path), content)

    def test_no_closing_delimiter(self):
        content = "---\ntitle: Test\nHello World"
        path = self._create_file("no_closing.md", content)
        self.assertEqual(read_text_from_file(path), content)

    def test_invalid_yaml(self):
        content = "---\ntitle: \"Unclosed string\n---\nHello World"
        path = self._create_file("invalid_yaml.md", content)
        self.assertEqual(read_text_from_file(path), content)

    def test_empty_frontmatter(self):
        content = "---\n---\nHello World"
        path = self._create_file("empty_fm.md", content)
        self.assertEqual(read_text_from_file(path), "Hello World")
        
    def test_crlf_line_endings(self):
        content = "---\r\ntitle: Test\r\n---\r\nHello World"
        path = self._create_file("crlf.md", content)
        self.assertEqual(read_text_from_file(path), "Hello World")


class TestHasFrontmatter(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data_has_fm"
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

    def tearDown(self):
        for f in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, f))
        os.rmdir(self.test_dir)

    def _create_file(self, filename, content):
        path = os.path.join(self.test_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_has_frontmatter_from_content_true(self):
        content = "---\ntitle: Test\n---\nHello"
        self.assertTrue(has_frontmatter_from_content(content))

    def test_has_frontmatter_from_content_false(self):
        content = "No frontmatter here."
        self.assertFalse(has_frontmatter_from_content(content))

    def test_has_frontmatter_from_content_malformed(self):
        content = "---\ntitle: Test\nHello" # No closing ---
        self.assertFalse(has_frontmatter_from_content(content))

    def test_has_frontmatter_from_file_true(self):
        content = "---\ntitle: Test\n---\nHello"
        path = self._create_file("valid.md", content)
        self.assertTrue(has_frontmatter_from_file(path))

    def test_has_frontmatter_from_file_false(self):
        content = "No frontmatter here."
        path = self._create_file("invalid.md", content)
        self.assertFalse(has_frontmatter_from_file(path))

    def test_has_frontmatter_from_file_nonexistent(self):
        self.assertFalse(has_frontmatter_from_file("nonexistent_file.md"))


class TestReadTextFromContent(unittest.TestCase):

    def test_with_valid_frontmatter(self):
        content = "---\ntitle: Test\n---\nHello World"
        self.assertEqual(read_text_from_content(content), "Hello World")

    def test_no_frontmatter(self):
        content = "Hello World"
        self.assertEqual(read_text_from_content(content), content)

    def test_empty_string(self):
        self.assertEqual(read_text_from_content(""), "")

    def test_only_frontmatter(self):
        content = "---\ntitle: Test\n---"
        self.assertEqual(read_text_from_content(content), "")

    def test_frontmatter_with_three_dashes_inside(self):
        content = "---\ntitle: Test\ncontent: ---\n---\nHello World"
        self.assertEqual(read_text_from_content(content), "Hello World")

    def test_malformed_frontmatter_start(self):
        content = " ---\ntitle: Test\n---\nHello World"
        self.assertEqual(read_text_from_content(content), content)

    def test_malformed_frontmatter_end(self):
        content = "---\ntitle: Test\n --- \nHello World"
        self.assertEqual(read_text_from_content(content), content)

    def test_no_closing_delimiter(self):
        content = "---\ntitle: Test\nHello World"
        self.assertEqual(read_text_from_content(content), content)

    def test_invalid_yaml(self):
        content = "---\ntitle: \"Unclosed string\n---\nHello World"
        self.assertEqual(read_text_from_content(content), content)

    def test_empty_frontmatter(self):
        content = "---\n---\nHello World"
        self.assertEqual(read_text_from_content(content), "Hello World")

    def test_crlf_line_endings(self):
        content = "---\r\ntitle: Test\r\n---\r\nHello World"
        self.assertEqual(read_text_from_content(content), "Hello World")


class TestFrontmatter(unittest.TestCase):

    def test_parse_frontmatter_valid(self):
        content = """---
title: Test
tags: [one, two]
---
# Content here
"""
        result = parse_frontmatter_from_content(content)
        expected = {
            'title': 'Test',
            'tags': ['one', 'two']
        }
        self.assertEqual(result, expected)

    def test_parse_frontmatter_invalid(self):
        # No frontmatter
        self.assertIsNone(parse_frontmatter_from_content("Just content"))
        
        # Invalid YAML
        content = """---
title: "unclosed string
---
content
"""
        self.assertIsNone(parse_frontmatter_from_content(content))
        
        # Missing end delimiter
        content = """---
title: Test
content
"""
        self.assertIsNone(parse_frontmatter_from_content(content))

    def test_frontmatter_to_text(self):
        frontmatter = {
            'title': 'Test',
            'tags': ['one', 'two'],
            'nested': {
                'key': 'value'
            }
        }
        result = frontmatter_to_text(frontmatter)
        expected = """---
title: Test
tags:
- one
- two
nested:
  key: value
---
"""
        self.assertEqual(result, expected)

    def test_update_frontmatter_existing(self):
        original = """---
title: Original
tags: [one]
---
# Content
More content
"""
        updates = {
            'tags': ['one', 'two'],
            'date': '2024-03-20'
        }
        
        result = update_frontmatter_in_content(original, updates)
        
        # Verify the updated frontmatter
        parsed = parse_frontmatter_from_content(result)
        self.assertEqual(parsed['title'], 'Original')  # Unchanged
        self.assertEqual(parsed['tags'], ['one', 'two'])  # Updated
        self.assertEqual(parsed['date'], '2024-03-20')  # Added
        
        # Verify content remains
        self.assertIn('# Content\nMore content', result)

    def test_update_frontmatter_no_existing(self):
        original = "# Just content\nMore content"
        updates = {'title': 'New', 'tags': ['test']}
        
        result = update_frontmatter_in_content(original, updates)
        
        # Verify the new frontmatter
        parsed = parse_frontmatter_from_content(result)
        self.assertEqual(parsed['title'], 'New')
        self.assertEqual(parsed['tags'], ['test'])
        
        # Verify content remains
        self.assertIn('# Just content\nMore content', result)

    def test_update_frontmatter_empty_updates(self):
        original = """---
title: Original
---
# Content
"""
        result = update_frontmatter_in_content(original, {})
        parsed = parse_frontmatter_from_content(result)
        self.assertEqual(parsed['title'], 'Original')
        self.assertIn('# Content', result)

    def test_unicode_handling(self):
        frontmatter = {
            'title': '测试',
            'author': 'José'
        }
        result = frontmatter_to_text(frontmatter)
        parsed = parse_frontmatter_from_content(result)
        self.assertEqual(parsed['title'], '测试')
        self.assertEqual(parsed['author'], 'José')

    def test_parse_frontmatter_empty_content(self):
        self.assertIsNone(parse_frontmatter_from_content(""))

    def test_parse_frontmatter_empty_fm_block(self):
        content = "---\n---\n# Content"
        self.assertEqual(parse_frontmatter_from_content(content), {})

    def test_update_frontmatter_with_dashes_in_content(self):
        original = """---
title: Original
---
# Content
--- with dashes ---
"""
        updates = {'author': 'Me'}
        result = update_frontmatter_in_content(original, updates)
        parsed = parse_frontmatter_from_content(result)
        self.assertEqual(parsed['title'], 'Original')
        self.assertEqual(parsed['author'], 'Me')
        self.assertIn('--- with dashes ---', result)

    def test_update_frontmatter_malformed_no_closing_delimiter(self):
        original = "---\ntitle: Malformed\n# Content"
        updates = {'author': 'Me'}
        result = update_frontmatter_in_content(original, updates)
        parsed = parse_frontmatter_from_content(result)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get('author'), 'Me')
        # The new frontmatter should be at the start, and the original content should still be there
        self.assertTrue(result.startswith('---\nauthor: Me\n---\n'))
        self.assertIn(original, result)

    def test_parse_frontmatter_with_dashes_in_value(self):
        content = """---
title: Title with --- in it
---
# Content
"""
        result = parse_frontmatter_from_content(content)
        expected = {'title': 'Title with --- in it'}
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()