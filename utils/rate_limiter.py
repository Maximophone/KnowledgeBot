"""Rate limiting utility for API calls and message sending."""

import json
import time
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any
from config.paths import PATHS
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class RateLimiter:
    def __init__(self, 
                 name: str,
                 min_delay_seconds: float = 2.0,
                 max_delay_seconds: float = 5.0,
                 max_per_day: int = 500):
        """Initialize rate limiter with configurable parameters.
        
        Args:
            name: Unique name for this rate limiter (used for persistent storage)
            min_delay_seconds: Minimum delay between operations
            max_delay_seconds: Maximum delay between operations (for jitter)
            max_per_day: Maximum number of operations per day
        """
        self.name = name
        self.min_delay = min_delay_seconds
        self.max_delay = max_delay_seconds
        self.max_per_day = max_per_day
        
        # Create rate limit directory if it doesn't exist
        self.rate_limit_dir = PATHS.data / "rate_limits"
        self.rate_limit_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize rate limiting from persistent storage
        self._init_rate_limiting()
    
    def _init_rate_limiting(self):
        """Initialize rate limiting data from persistent storage."""
        self.rate_limit_file = self.rate_limit_dir / f"{self.name}_rate_limit.json"
        
        # Default rate limit data
        self.rate_limit_data = {
            "date": str(date.today()),
            "operations_count": 0,
            "last_operation_time": None
        }
        
        # Load existing data if available
        if self.rate_limit_file.exists():
            try:
                with open(self.rate_limit_file, 'r') as f:
                    stored_data = json.load(f)
                
                # Reset counter if it's a new day
                if stored_data["date"] == str(date.today()):
                    self.rate_limit_data = stored_data
                else:
                    # It's a new day, save default data
                    self._save_rate_limit_data()
            except Exception as e:
                logger.error(f"Error loading rate limit data: {e}")
                # Use default data and save it
                self._save_rate_limit_data()
        else:
            # No existing data, save default data
            self._save_rate_limit_data()
    
    def _save_rate_limit_data(self):
        """Save rate limiting data to persistent storage."""
        try:
            with open(self.rate_limit_file, 'w') as f:
                json.dump(self.rate_limit_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving rate limit data: {e}")
    
    def wait(self):
        """Implement rate limiting logic between operations.
        
        Raises:
            Exception if daily limit is reached
        """
        current_time = time.time()
        
        # Check if we've hit the daily limit
        if self.rate_limit_data["operations_count"] >= self.max_per_day:
            raise Exception(
                f"Daily limit of {self.max_per_day} operations reached for {self.name}. "
                f"Please try again tomorrow."
            )
        
        # If this isn't the first operation, ensure minimum delay
        if self.rate_limit_data["last_operation_time"] is not None:
            time_since_last = current_time - self.rate_limit_data["last_operation_time"]
            if time_since_last < self.min_delay:
                # Calculate required wait time
                wait_time = self.min_delay - time_since_last
                # Add some random jitter only if max_delay > min_delay
                if self.max_delay > self.min_delay:
                    jitter = time.time() % (self.max_delay - self.min_delay)
                    total_wait = wait_time + jitter
                else:
                    total_wait = wait_time
                
                logger.debug(f"Rate limiting: waiting {total_wait:.1f} seconds...")
                time.sleep(total_wait)
        
        # Update rate limit data
        self.rate_limit_data["last_operation_time"] = time.time()
        self.rate_limit_data["operations_count"] += 1
        self._save_rate_limit_data()
        
        logger.debug(
            f"Operations today for {self.name}: "
            f"{self.rate_limit_data['operations_count']}/{self.max_per_day}"
        ) 