import unittest
from tag_parser import process_tags

class TestParseTags(unittest.TestCase):

    def test_parse_tags(self):
        content = """
Some text here
<tag1!value1>Some inner text</tag1!>
More text
<tag2!"quoted value with spaces">
<tag3!123>
<tag4!"multi
line
value">Multiline content
spanning multiple
lines</tag4!>
<tag5!empty_value>
<tag6!"value with \\"escaped\\" quotes">
        """

        expected = [
            ('tag1', 'value1', 'Some inner text'),
            ('tag2', 'quoted value with spaces', None),
            ('tag3', '123', None),
            ('tag4', 'multi\nline\nvalue', 'Multiline content\nspanning multiple\nlines'),
            ('tag5', 'empty_value', None),
            ('tag6', 'value with \\"escaped\\" quotes', None)
        ]

        _, result = process_tags(content)
        self.assertEqual(result, expected)

    def test_empty_content(self):
        content = ""
        _, result = process_tags(content)
        self.assertEqual(result, [])

    def test_no_tags(self):
        content = "This is some content without any tags."
        _, result = process_tags(content)
        self.assertEqual(result, [])

    def test_nested_tags(self):
        content = '<outer!value>test <inner!"nested value">Inner content</inner!> more text</outer!>'
        expected = [
            ('outer', 'value', 'test <inner!"nested value">Inner content</inner!> more text'),
        ]
        _, result = process_tags(content)
        self.assertEqual(result, expected)

    def test_malformed_tags(self):
        content = """
        <incomplete!value
        <mismatched!"value with spaces">content</mismatch!>
        <correct!value>This is correct</correct!>
        """
        expected = [
            ('mismatched', 'value with spaces', None),
            ('correct', 'value', 'This is correct')
        ]
        _, result = process_tags(content)
        self.assertEqual(result, expected)

    def test_only_outermost(self):
        content = "<name!value> test <another!>blah</another!> </name!>"
        expected = [
            ('name', 'value', ' test <another!>blah</another!> ')
        ]
        _, result = process_tags(content)
        self.assertEqual(result, expected)

    def test_no_value_tag(self):
        content = "<name!>This is a tag with no value</name!>"
        expected = [
            ('name', None, 'This is a tag with no value')
        ]
        _, result = process_tags(content)
        self.assertEqual(result, expected)

    def test_empty_tag(self):
        content = "<name!>"
        expected = [
            ('name', None, None)
        ]
        _, result = process_tags(content)
        self.assertEqual(result, expected)
    
    def test_obs_format(self):
        content = """
        <name![[value]]>
        <name2![[value]]>text</name2!>
        <name!"[[value]]">
        <name2![value]>text</name2!>
        <name![[value value]]>
        """
        expected = [
            ("name", "[[value]]", None),
            ("name2", "[[value]]", "text"),
            ("name", "[[value]]", None),
            ("name2", "[value]", "text"),
            ("name", "[[value value]]", None)
            ]
        _, result = process_tags(content)
        self.assertEqual(result, expected)

    def test_no_replace(self):
        content = """<name!value>test</name!>"""
        expected_params = [
            ("name", "value", "test")
        ]
        result_txt, params = process_tags(content)
        self.assertEqual(result_txt, content)
        self.assertEqual(params, expected_params)

    def test_replace(self):
        content = """
        <rep!>
        <norep!>test</norep!>
        <outside!>plop<inside!></outside!>
        <another!test> this is some text blah </another!>
        <blah!test>more text</blah!>
        """
        expected_txt = """
        replaced
        <norep!>test</norep!>
        <outside!>plop<inside!></outside!>
        test
        <blah!test>more text</blah!>
        """
        expected_params = [
            ('rep', None, None),
            ('norep', None, 'test'),
            ('outside', None, 'plop<inside!>'),
            ('another', 'test', ' this is some text blah '),
            ('blah', 'test', 'more text'),
        ]
        result_txt, params = process_tags(content, {
            "rep": lambda v, t, c: "replaced", 
            "indide": lambda v, t, c: "should not appear",
            "another": lambda v, t, c: v,
            })
        self.assertEqual(result_txt, expected_txt)
        self.assertEqual(params, expected_params)

    def test_same_names(self):
        content = """
        <ai!rep>test</ai!>
        <ai!>test2</ai!>
        """
        expected_params = [
            ("ai", "rep", "test"),
            ("ai", None, "test2")
        ]
        _, params = process_tags(content)
        self.assertEqual(params, expected_params)

if __name__ == '__main__':
    unittest.main()