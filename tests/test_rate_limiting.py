import unittest
import logging
import time
from unittest.mock import patch, MagicMock
import google.generativeai as genai

from ai_core.client import AI
from utils.rate_limiter import ReactiveRateLimiter
from ai_core.wrappers.google import GeminiWrapper
from ai_core.types import Message, MessageContent

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RateLimitError(Exception):
    """Mock exception for rate limit errors."""
    def __init__(self, message="Rate limit exceeded", status_code=429):
        self.status_code = status_code
        super().__init__(message)

class MockResponse:
    """Mock response from the Gemini API."""
    def __init__(self, text):
        self.text = text

class TestRateLimiting(unittest.TestCase):
    """End-to-end tests for rate limiting functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "fake_api_key"
        self.model_name = "gemini-1.5-pro-latest"
        
        # Create a patch for the genai.GenerativeModel.generate_content method
        self.generate_patch = patch('google.generativeai.GenerativeModel.generate_content')
        self.mock_generate = self.generate_patch.start()
        
        # Create a patch for genai.configure
        self.configure_patch = patch('google.generativeai.configure')
        self.mock_configure = self.configure_patch.start()
        
        # Create a patch for the get_client function to return our own instance
        self.get_client_patch = patch('ai.models.get_client')
        self.mock_get_client = self.get_client_patch.start()
        
    def tearDown(self):
        """Tear down test fixtures."""
        self.generate_patch.stop()
        self.configure_patch.stop()
        self.get_client_patch.stop()

    def test_successful_request_without_rate_limiting(self):
        """Test a successful request without rate limiting."""
        # Mock a successful response
        self.mock_generate.return_value = MockResponse("This is a successful response")
        
        # Create a wrapper with rate limiting disabled
        wrapper = GeminiWrapper(self.api_key, self.model_name, rate_limiting=False)
        self.mock_get_client.return_value = wrapper
        
        # Create the AI client
        client = AI(model_identifier="gemini1.5", rate_limiting=False)
        
        # Make a request
        response = client.message("Hello, world!")
        
        # Verify the response
        self.assertEqual(response.content, "This is a successful response")
        self.mock_generate.assert_called_once()

    def test_rate_limit_retry_success(self):
        """Test a rate-limited request that succeeds after retrying."""
        # Mock a rate limit error followed by a successful response
        self.mock_generate.side_effect = [
            RateLimitError("Rate limit exceeded"),
            MockResponse("Success after retry")
        ]
        
        # Create a custom rate limiter for the test
        rate_limiter = ReactiveRateLimiter(
            name="test_limiter",
            initial_backoff_seconds=0.1,  # Very small value for faster tests
            max_retries=3
        )
        
        # Create a wrapper with rate limiting enabled
        wrapper = GeminiWrapper(
            self.api_key, 
            self.model_name, 
            rate_limiting=True,
            rate_limiter=rate_limiter
        )
        self.mock_get_client.return_value = wrapper
        
        # Create the AI client and pass the rate limiter explicitly
        client = AI(model_identifier="gemini1.5", rate_limiting=True, rate_limiter=rate_limiter)
        
        # Make a request
        start_time = time.time()
        response = client.message("Hello, world!")
        elapsed_time = time.time() - start_time
        
        # Verify the response and retry behavior
        self.assertEqual(response.content, "Success after retry")
        self.assertEqual(self.mock_generate.call_count, 2)
        # Should have waited at least the initial backoff
        self.assertGreaterEqual(elapsed_time, 0.05)  # Half the initial backoff is sufficient

    def test_rate_limit_progressive_backoff(self):
        """Test that backoff increases with multiple rate limit errors."""
        # Mock multiple rate limit errors followed by a success
        self.mock_generate.side_effect = [
            RateLimitError("Rate limit error 1"),
            RateLimitError("Rate limit error 2"),
            MockResponse("Success after multiple retries")
        ]
        
        # Create a rate limiter with known backoff parameters
        rate_limiter = ReactiveRateLimiter(
            name="test_progressive_limiter",
            initial_backoff_seconds=0.1,  # Very small value for faster tests
            backoff_factor=2.0,
            max_retries=3
        )
        
        # Create a wrapper with our rate limiter
        wrapper = GeminiWrapper(
            self.api_key, 
            self.model_name, 
            rate_limiting=True,
            rate_limiter=rate_limiter
        )
        self.mock_get_client.return_value = wrapper
        
        # Create the AI client
        client = AI(model_identifier="gemini1.5", rate_limiting=True, rate_limiter=rate_limiter)
        
        # Make a request
        start_time = time.time()
        response = client.message("Hello, world!")
        elapsed_time = time.time() - start_time
        
        # Verify the response and progressive backoff
        self.assertEqual(response.content, "Success after multiple retries")
        self.assertEqual(self.mock_generate.call_count, 3)
        
        # First retry should wait 0.1s, second retry should wait 0.2s (0.1 * 2.0)
        # Total should be at least 0.3s
        self.assertGreaterEqual(elapsed_time, 0.15)  # Half of expected delay for test stability
        
        # Check if the rate limiter recorded the correct number of failures
        self.assertEqual(rate_limiter.get_retry_count(), 2)

    def test_exceed_max_retries(self):
        """Test behavior when maximum retries are exceeded."""
        # Mock multiple rate limit errors exceeding max retries
        self.mock_generate.side_effect = RateLimitError("Rate limit exceeded")
        
        # Create a rate limiter with a small number of retries
        rate_limiter = ReactiveRateLimiter(
            name="test_max_retries_limiter",
            initial_backoff_seconds=0.1,  # Very small value for faster tests
            max_retries=2
        )
        
        # Create a wrapper with our rate limiter
        wrapper = GeminiWrapper(
            self.api_key, 
            self.model_name, 
            rate_limiting=True,
            rate_limiter=rate_limiter
        )
        self.mock_get_client.return_value = wrapper
        
        # Create the AI client
        client = AI(model_identifier="gemini1.5", rate_limiting=True, rate_limiter=rate_limiter)
        
        # Make a request and expect it to fail after retries
        with self.assertRaises(Exception) as context:
            client.message("Hello, world!")
        
        # Verify that the rate limiter reached max retries
        self.assertTrue(rate_limiter.exceeded_max_retries())
        self.assertEqual(rate_limiter.get_retry_count(), 2)
        
        # Verify that the exception has the rate limit information
        exception = context.exception
        self.assertTrue(hasattr(exception, 'rate_limit_exceeded'))
        self.assertTrue(exception.rate_limit_exceeded)
        self.assertIn('retry_count', exception.retry_info)
        self.assertEqual(exception.retry_info['retry_count'], 2)

    def test_different_error_types(self):
        """Test that non-rate-limit errors are not retried."""
        # Mock a different type of error
        self.mock_generate.side_effect = ValueError("Some other error")
        
        # Create a rate limiter
        rate_limiter = ReactiveRateLimiter(
            name="test_error_types_limiter",
            initial_backoff_seconds=0.1,  # Very small value for faster tests
            max_retries=3
        )
        
        # Create a wrapper with our rate limiter
        wrapper = GeminiWrapper(
            self.api_key, 
            self.model_name, 
            rate_limiting=True,
            rate_limiter=rate_limiter
        )
        self.mock_get_client.return_value = wrapper
        
        # Create the AI client
        client = AI(model_identifier="gemini1.5", rate_limiting=True, rate_limiter=rate_limiter)
        
        # Make a request and expect the original error
        with self.assertRaises(ValueError):
            client.message("Hello, world!")
        
        # Verify that the rate limiter didn't record any retries
        self.assertEqual(rate_limiter.get_retry_count(), 0)
        self.mock_generate.assert_called_once()

    def test_reset_after_success(self):
        """Test that the rate limiter resets properly after a successful request."""
        # First mock a rate limit error, then success
        self.mock_generate.side_effect = [
            RateLimitError("Rate limit error"),
            MockResponse("Success after retry"),
            # For the second message:
            MockResponse("Second message success")
        ]
        
        # Create a rate limiter
        rate_limiter = ReactiveRateLimiter(
            name="test_reset_limiter",
            initial_backoff_seconds=0.1,  # Very small value for faster tests
            max_retries=3
        )
        
        # Create a wrapper with our rate limiter
        wrapper = GeminiWrapper(
            self.api_key, 
            self.model_name, 
            rate_limiting=True,
            rate_limiter=rate_limiter
        )
        self.mock_get_client.return_value = wrapper
        
        # Create the AI client
        client = AI(model_identifier="gemini1.5", rate_limiting=True, rate_limiter=rate_limiter)
        
        # Make a first request that hits rate limit then succeeds
        response1 = client.message("First message")
        self.assertEqual(response1.content, "Success after retry")
        self.assertEqual(rate_limiter.get_retry_count(), 1)
        
        # Record that a retry happened
        had_failures = rate_limiter.get_status_info()['has_had_failures']
        self.assertTrue(had_failures)
        
        # Reset the rate limiter
        rate_limiter.reset_retries()
        
        # Make a second request that should succeed immediately
        response2 = client.message("Second message")
        self.assertEqual(response2.content, "Second message success")
        
        # Verify the rate limiter was reset
        self.assertEqual(rate_limiter.get_retry_count(), 0)
        self.assertFalse(rate_limiter.get_status_info()['has_had_failures'])

    def test_custom_rate_limiter_parameters(self):
        """Test using custom parameters for the rate limiter."""
        # Mock multiple rate limit errors followed by a success
        self.mock_generate.side_effect = [
            RateLimitError("Rate limit error 1"),
            RateLimitError("Rate limit error 2"),
            RateLimitError("Rate limit error 3"),
            RateLimitError("Rate limit error 4"),
            MockResponse("Success after many retries")
        ]
        
        # Create a rate limiter with generous retry settings
        rate_limiter = ReactiveRateLimiter(
            name="test_custom_params_limiter",
            initial_backoff_seconds=0.1,  # Very small value for faster tests
            backoff_factor=1.5,
            max_backoff_seconds=1.0,  # Smaller cap for faster tests
            max_retries=5
        )
        
        # Create a wrapper with our rate limiter
        wrapper = GeminiWrapper(
            self.api_key, 
            self.model_name, 
            rate_limiting=True,
            rate_limiter=rate_limiter
        )
        self.mock_get_client.return_value = wrapper
        
        # Create the AI client
        client = AI(model_identifier="gemini1.5", rate_limiting=True, rate_limiter=rate_limiter)
        
        # Make a request
        response = client.message("Hello, world!")
        
        # Verify successful response after multiple retries
        self.assertEqual(response.content, "Success after many retries")
        self.assertEqual(self.mock_generate.call_count, 5)
        self.assertEqual(rate_limiter.get_retry_count(), 4)
        
        # Check backoff calculations
        status = rate_limiter.get_status_info()
        # After 4 backoffs with factor 1.5, should be at 0.1 * (1.5^4) = ~0.5s
        # But capped at 1s by max_backoff_seconds
        self.assertLessEqual(status['current_backoff'], 1.0)

    def test_gradual_backoff_reduction(self):
        """Test that the backoff is gradually reduced after successful calls."""
        # Create a rate limiter with known parameters for testing
        rate_limiter = ReactiveRateLimiter(
            name="test_recovery_limiter",
            initial_backoff_seconds=0.1,  # Start with 0.1s
            backoff_factor=2.0,          # Double on failure
            recovery_factor=2.0,         # Halve on success
            max_retries=5
        )
        
        # Simulate rate limit errors to build up the backoff
        rate_limiter.record_failure()  # Should set backoff to 0.1s
        self.assertEqual(rate_limiter.get_current_backoff(), 0.1)
        
        rate_limiter.record_failure()  # Should increase to 0.2s
        self.assertEqual(rate_limiter.get_current_backoff(), 0.2)
        
        # Now record successes and check backoff reduction
        rate_limiter.record_success()  # Should reduce to 0.1s
        self.assertEqual(rate_limiter.get_current_backoff(), 0.1)
        
        rate_limiter.record_success()  # Should reduce to 0.05s
        self.assertEqual(rate_limiter.get_current_backoff(), 0.05)
        
        rate_limiter.record_success()  # Should reduce to 0.025s
        self.assertEqual(rate_limiter.get_current_backoff(), 0.025)
        
        # After enough successes and zero backoff, has_had_failures should be reset
        # We need a few more successful calls to reach zero
        rate_limiter.record_success()  # 0.0125
        rate_limiter.record_success()  # ~0.00625
        rate_limiter.record_success()  # ~0.003125 (essentially 0 with float precision)
        
        # After 3 consecutive successes with backoff at 0, has_had_failures should reset
        # Check that backoff is close to zero (not exactly zero due to floating point precision)
        self.assertLess(rate_limiter.get_current_backoff(), 0.01)
        self.assertEqual(rate_limiter.get_status_info()['consecutive_successes'], 6)
        
        # Add one more successful call to trigger the reset
        rate_limiter.record_success()
        
        # Verify has_had_failures is now False and retry_count is reset
        status = rate_limiter.get_status_info()
        self.assertFalse(status['has_had_failures'])
        self.assertEqual(status['retry_count'], 0)

    def test_mixed_success_failure_pattern(self):
        """Test a more realistic pattern of intermixed successes and failures."""
        # Create a rate limiter
        rate_limiter = ReactiveRateLimiter(
            name="test_mixed_pattern_limiter",
            initial_backoff_seconds=0.1,
            backoff_factor=2.0,
            recovery_factor=1.5,  # Slower recovery
            max_retries=5
        )
        
        # Simulate a series of intermixed failures and successes
        rate_limiter.record_failure()  # 0.1s
        self.assertEqual(rate_limiter.get_current_backoff(), 0.1)
        
        rate_limiter.record_success()  # Should reduce to ~0.067s
        self.assertAlmostEqual(rate_limiter.get_current_backoff(), 0.1 / 1.5, places=3)
        
        rate_limiter.record_failure()  # Should increase to ~0.133s
        self.assertAlmostEqual(rate_limiter.get_current_backoff(), (0.1 / 1.5) * 2.0, places=3)
        
        rate_limiter.record_success()  # Should reduce to ~0.089s
        self.assertAlmostEqual(rate_limiter.get_current_backoff(), ((0.1 / 1.5) * 2.0) / 1.5, places=3)
        
        rate_limiter.record_success()  # Should reduce further
        rate_limiter.record_success()  # Should reduce further
        
        # Consecutive successes should be tracked
        self.assertEqual(rate_limiter.get_status_info()['consecutive_successes'], 3)
        
        # Another failure should reset consecutive successes
        rate_limiter.record_failure()
        self.assertEqual(rate_limiter.get_status_info()['consecutive_successes'], 0)

if __name__ == '__main__':
    unittest.main() 