import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile
import base64

# Import the functions and classes you want to test
from ai import (
    encode_image, validate_image, extract_text_from_pdf, n_tokens,
    count_tokens_input, count_tokens_output, log_token_use,
    AIWrapper, ClaudeWrapper, GeminiWrapper, GPTWrapper, MockWrapper,
    get_client, get_model, AI, AIResponse
)

IMG1_PATH = "G:\\My Drive\\Obsidian\\Images\\cube.png"
IMG2_PATH = "G:\\My Drive\\Obsidian\\Images\\cube.png"

class TestAIFunctions(unittest.TestCase):

    def test_n_tokens(self):
        self.assertEqual(n_tokens("Hello, world!"), 3)
        self.assertEqual(n_tokens(""), 0)

    def test_count_tokens_input(self):
        messages = [{"content": "Hello"}, {"content": "World"}]
        system_prompt = "System"
        self.assertEqual(count_tokens_input(messages, system_prompt), 4)

    def test_count_tokens_images(self):
        encoded_image, media_type = encode_image(IMG1_PATH)
        messages = [
            {"content": "Hello"}, 
            {"content": [
                {
                    "type": "image", 
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": encoded_image
                        }
                }
                ]
            }
        ]
        self.assertEqual(count_tokens_input(messages, ""), 85)

    def test_count_tokens_input(self):
        messages = [{"content": "Hello"}, {"content": "World"}]
        system_prompt = "System"
        self.assertEqual(count_tokens_input(messages, system_prompt), 4)

    def test_count_tokens_output(self):
        self.assertEqual(count_tokens_output("Hello, world!"), 3)

    @patch('ai.open')
    def test_log_token_use(self, mock_open):
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        log_token_use("model1", 100, input=True)
        mock_file.write.assert_called_once()

    @patch('ai.imghdr.what')
    @patch('ai.open')
    def test_encode_image(self, mock_open, mock_imghdr):
        mock_imghdr.return_value = 'jpeg'
        mock_file = MagicMock()
        mock_file.read.return_value = b'image_data'
        mock_open.return_value.__enter__.return_value = mock_file
        
        encoded, media_type = encode_image('test.jpg')
        self.assertEqual(media_type, 'image/jpeg')
        self.assertEqual(encoded, base64.b64encode(b'image_data').decode('utf-8'))

    def test_validate_image(self):
        with tempfile.NamedTemporaryFile(suffix='.jpg') as temp_file:
            temp_file.write(b'fake image data')
            temp_file.flush()
            
            # Should not raise an exception
            validate_image(temp_file.name)
            
            # Test file not found
            with self.assertRaises(FileNotFoundError):
                validate_image('nonexistent.jpg')
            
            # Test file too large
            with patch('os.path.getsize', return_value=30*1024*1024):
                with self.assertRaises(ValueError):
                    validate_image(temp_file.name)

    @patch('ai.fitz.open')
    def test_extract_text_from_pdf(self, mock_fitz_open):
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = [('', '', '', '', 'Sample text\nwith newlines')]
        mock_doc.__enter__.return_value = [mock_page]
        mock_fitz_open.return_value = mock_doc

        result = extract_text_from_pdf('test.pdf')
        self.assertEqual(result, 'Sample text with newlines')

class TestAIWrappers(unittest.TestCase):

    def test_ai_wrapper(self):
        wrapper = AIWrapper()
        with self.assertRaises(NotImplementedError):
            wrapper._messages('model', [], '', 100, 0.5)

    @patch('ai.anthropic.Client')
    def test_claude_wrapper(self, mock_client):
        mock_client.return_value.messages.create.return_value.content = [MagicMock(text='Response')]
        wrapper = ClaudeWrapper('fake_key')
        response = wrapper._messages('model', [], '', 100, 0.5)
        self.assertEqual(response, 'Response')

    @patch('ai.genai.GenerativeModel')
    def test_gemini_wrapper(self, mock_model):
        mock_model.return_value.generate_content.return_value.text = 'Response'
        wrapper = GeminiWrapper('fake_key', 'model-name')
        response = wrapper._messages('model', [{'role': 'user', 'content': 'Hello'}], '', 100, 0.5)
        self.assertEqual(response, 'Response')

    @patch('ai.OpenAI')
    def test_gpt_wrapper(self, mock_openai):
        mock_openai.return_value.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content='Response'))
        ]
        wrapper = GPTWrapper('fake_key', 'org')
        response = wrapper._messages('model', [], '', 100, 0.5)
        self.assertEqual(response, 'Response')

    def test_mock_wrapper(self):
        wrapper = MockWrapper()
        response = wrapper._messages('model', [{'role': 'user', 'content': 'Hello'}], 'System', 100, 0.5)
        self.assertIn('Hello', response)
        self.assertIn('System', response)

class TestAIClass(unittest.TestCase):

    @patch('ai.get_client')
    @patch('ai.get_model')
    def test_ai_init(self, mock_get_model, mock_get_client):
        mock_get_model.return_value = 'model'
        mock_get_client.return_value = MagicMock()
        ai = AI('mock')
        self.assertEqual(ai.model_name, 'model')
        self.assertIsNotNone(ai.client)

    def test_prepare_messages(self):
        ai = AI('mock')
        messages = ai._prepare_messages('Hello', [IMG1_PATH, IMG2_PATH])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['role'], 'user')
        self.assertIsInstance(messages[0]['content'], list)
        self.assertEqual(len(messages[0]['content']), 3)  # 2 images + 1 text

    @patch('ai.AIWrapper.messages')
    def test_ai_message(self, mock_messages):
        mock_messages.return_value = AIResponse(content='Response')
        ai = AI('mock')
        response = ai.message('Hello', image_paths=[IMG1_PATH])
        self.assertEqual(response.content, 'Response')

    @patch('ai.AIWrapper.messages')
    def test_ai_conversation(self, mock_messages):
        mock_messages.return_value = AIResponse(content='Response')
        ai = AI('mock')
        response = ai.conversation('Hello', image_paths=[IMG1_PATH])
        self.assertEqual(response.content, 'Response')
        self.assertEqual(len(ai._history), 2)

if __name__ == '__main__':
    unittest.main()