import unittest
from unittest.mock import patch, MagicMock
from obsidian.obsidian_ai import process_conversation, beacon_ai, beacon_me, REPLACEMENTS_INSIDE, validate_image, encode_image

class TestProcessConversation(unittest.TestCase):

    def setUp(self):
        self.mock_validate_image = MagicMock()
        self.mock_encode_image = MagicMock(return_value=('base64_encoded_image', 'image/jpeg'))

    @patch('obsidian_ai.validate_image')
    @patch('obsidian_ai.encode_image')
    def test_basic_conversation(self, mock_encode_image, mock_validate_image):
        mock_validate_image.side_effect = self.mock_validate_image
        mock_encode_image.side_effect = self.mock_encode_image

        conversation = f"User question{beacon_ai}Assistant answer{beacon_me}User follow-up"
        result = process_conversation(conversation)

        expected = [
            {"role": "user", "content": "User question"},
            {"role": "assistant", "content": "Assistant answer"},
            {"role": "user", "content": "User follow-up"}
        ]
        self.assertEqual(result, expected)

    @patch('obsidian_ai.validate_image')
    @patch('obsidian_ai.encode_image')
    def test_conversation_with_image(self, mock_encode_image, mock_validate_image):
        mock_validate_image.side_effect = self.mock_validate_image
        mock_encode_image.side_effect = self.mock_encode_image

        conversation = f"<image!cube.png> User question{beacon_ai}Assistant answer{beacon_me}User follow-up"
        result = process_conversation(conversation)

        expected = [
            {"role": "user", "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": "base64_encoded_image"
                    }
                },
                {"type": "text", "text": "User question"}
            ]},
            {"role": "assistant", "content": "Assistant answer"},
            {"role": "user", "content": "User follow-up"}
        ]
        self.assertEqual(result, expected)

    @patch('obsidian_ai.validate_image')
    @patch('obsidian_ai.encode_image')
    def test_conversation_with_multiple_images(self, mock_encode_image, mock_validate_image):
        mock_validate_image.side_effect = self.mock_validate_image
        mock_encode_image.side_effect = self.mock_encode_image

        conversation = f"<image!cube.png> User question <image!cube.png>{beacon_ai}Assistant answer{beacon_me}User follow-up"
        result = process_conversation(conversation)

        expected = [
            {"role": "user", "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": "base64_encoded_image"
                    }
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": "base64_encoded_image"
                    }
                },
                {"type": "text", "text": "User question"}
            ]},
            {"role": "assistant", "content": "Assistant answer"},
            {"role": "user", "content": "User follow-up"}
        ]
        self.assertEqual(result, expected)

    @patch('obsidian_ai.validate_image')
    @patch('obsidian_ai.encode_image')
    def test_conversation_with_image_processing_error(self, mock_encode_image, mock_validate_image):
        mock_validate_image.side_effect = ValueError("Invalid image")
        mock_encode_image.side_effect = self.mock_encode_image

        conversation = f"<image!cube.png> User question{beacon_ai}Assistant answer{beacon_me}User follow-up"
        result = process_conversation(conversation)

        expected = [
            {'role': 'user', 'content': [{'type': 'text', 'text': 'User question'}]},
            {"role": "assistant", "content": "Assistant answer"},
            {"role": "user", "content": "User follow-up"}
        ]
        self.assertEqual(result, expected)

    def test_conversation_starting_with_assistant(self):
        conversation = f"Assistant start{beacon_me}User response"
        with self.assertRaises(AssertionError):
            result = process_conversation(conversation)

    def test_empty_conversation(self):
        conversation = ""
        with self.assertRaises(AssertionError):
            process_conversation(conversation)

    def test_invalid_conversation_format(self):
        conversation = f"User{beacon_ai}Assistant{beacon_ai}User"
        with self.assertRaises(AssertionError):
            process_conversation(conversation)

if __name__ == '__main__':
    unittest.main()