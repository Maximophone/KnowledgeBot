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
from processors.common.frontmatter import parse_frontmatter, frontmatter_to_text, update_frontmatter

class TestFrontmatter(unittest.TestCase):

    def test_parse_frontmatter_valid(self):
        content = """---
title: Test
tags: [one, two]
---
# Content here
"""
        result = parse_frontmatter(content)
        expected = {
            'title': 'Test',
            'tags': ['one', 'two']
        }
        self.assertEqual(result, expected)

    def test_parse_frontmatter_invalid(self):
        # No frontmatter
        self.assertIsNone(parse_frontmatter("Just content"))
        
        # Invalid YAML
        content = """---
title: "unclosed string
---
content
"""
        self.assertIsNone(parse_frontmatter(content))
        
        # Missing end delimiter
        content = """---
title: Test
content
"""
        self.assertIsNone(parse_frontmatter(content))

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
        
        result = update_frontmatter(original, updates)
        
        # Verify the updated frontmatter
        parsed = parse_frontmatter(result)
        self.assertEqual(parsed['title'], 'Original')  # Unchanged
        self.assertEqual(parsed['tags'], ['one', 'two'])  # Updated
        self.assertEqual(parsed['date'], '2024-03-20')  # Added
        
        # Verify content remains
        self.assertIn('# Content\nMore content', result)

    def test_update_frontmatter_no_existing(self):
        original = "# Just content\nMore content"
        updates = {'title': 'New', 'tags': ['test']}
        
        result = update_frontmatter(original, updates)
        
        # Verify the new frontmatter
        parsed = parse_frontmatter(result)
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
        result = update_frontmatter(original, {})
        parsed = parse_frontmatter(result)
        self.assertEqual(parsed['title'], 'Original')
        self.assertIn('# Content', result)

    def test_unicode_handling(self):
        frontmatter = {
            'title': '测试',
            'author': 'José'
        }
        result = frontmatter_to_text(frontmatter)
        parsed = parse_frontmatter(result)
        self.assertEqual(parsed['title'], '测试')
        self.assertEqual(parsed['author'], 'José')

if __name__ == '__main__':
    unittest.main()