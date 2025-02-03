"""Rate limiting utility for API calls and message sending."""

import json
import time
import logging
from datetime import datetime, date, time as dt_time
from pathlib import Path
from typing import Dict, Any
from config.paths import PATHS
from config.logging_config import setup_logger
import random

logger = setup_logger(__name__)

class RateLimiter:
    def __init__(self, 
                 name: str,
                 min_delay_seconds: float = 2.0,
                 max_delay_seconds: float = 5.0,
                 max_per_day: int = 500,
                 night_mode: bool = True,
                 backoff_factor: float = 2.0,
                 max_backoff_seconds: float = 300.0):  # 5 minutes max backoff
        """Initialize rate limiter with configurable parameters.
        
        Args:
            name: Unique name for this rate limiter (used for persistent storage)
            min_delay_seconds: Minimum delay between operations
            max_delay_seconds: Maximum delay between operations (for jitter)
            max_per_day: Maximum number of operations per day
            night_mode: Whether to pause operations during night hours
            backoff_factor: Multiplier for exponential backoff on failures
            max_backoff_seconds: Maximum backoff delay in seconds
        """
        self.name = name
        self.min_delay = min_delay_seconds
        self.max_delay = max_delay_seconds
        self.max_per_day = max_per_day
        self.night_mode = night_mode
        self.backoff_factor = backoff_factor
        self.max_backoff_seconds = max_backoff_seconds
        
        # Track consecutive failures for backoff
        self.consecutive_failures = 0
        self.current_backoff = min_delay_seconds
        
        # Night mode time settings
        self.night_start = dt_time(hour=0, minute=30)  # 12:30 AM (00:30)
        self.morning_start = dt_time(hour=7, minute=30)  # 7:30 AM
        self.morning_end = dt_time(hour=8, minute=0)    # 8:00 AM
        
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
    
    def _is_night_time(self) -> bool:
        """Check if current time is during night hours."""
        current_time = datetime.now().time()
        # Night time is between 00:30 and 07:30
        return self.night_start <= current_time < self.morning_start

    def _get_morning_resume_time(self) -> float:
        """Calculate seconds to wait until morning resume time."""
        now = datetime.now()
        current_date = now.date()
        
        # If it's after midnight, use today's date, otherwise use tomorrow
        if now.time() >= self.night_start:
            resume_date = current_date.replace(day=current_date.day + 1)
        else:
            resume_date = current_date
        
        # Random minutes between morning_start and morning_end
        random_minutes = random.randint(0, 30)  # 30 minutes window
        resume_time = datetime.combine(resume_date, self.morning_start)
        resume_time = resume_time.replace(minute=resume_time.minute + random_minutes)
        
        return (resume_time - now).total_seconds()

    def wait(self) -> bool:
        """Implement rate limiting logic between operations.
        
        Returns:
            bool: True if the operation should proceed, False if daily limit reached
        
        Raises:
            Exception: If during night hours
        """
        current_time = time.time()
        
        # Check night mode restrictions
        if self.night_mode and self._is_night_time():
            wait_time = self._get_morning_resume_time()
            logger.info(
                f"Night mode active for {self.name}. "
                f"Pausing operations for {wait_time/3600:.1f} hours."
            )
            time.sleep(wait_time+10)
            logger.info(f"Resuming operations for {self.name}")
            # Reset daily counters as it's a new day
            self.rate_limit_data = {
                "date": str(date.today()),
                "operations_count": 0,
                "last_operation_time": None
            }
            self._save_rate_limit_data()
            return self.wait()  # Recursive call to recheck conditions
        
        # Check if we've hit the daily limit
        if self.rate_limit_data["operations_count"] >= self.max_per_day:
            logger.warning(
                f"Daily limit reached for {self.name}: "
                f"{self.rate_limit_data['operations_count']}/{self.max_per_day} operations"
            )
            return False
        
        # Calculate delay with backoff if there were failures
        base_delay = max(self.min_delay, self.current_backoff)
        
        if self.rate_limit_data["last_operation_time"] is not None:
            time_since_last = current_time - self.rate_limit_data["last_operation_time"]
            if time_since_last < base_delay:
                wait_time = base_delay - time_since_last
                # Add jitter only if max_delay > current delay
                if self.max_delay > base_delay:
                    jitter = random.uniform(0, self.max_delay - base_delay)
                    total_wait = wait_time + jitter
                else:
                    total_wait = wait_time
                
                logger.info(
                    f"Rate limiting for {self.name}: waiting {total_wait:.1f} seconds. "
                    f"Operations today: {self.rate_limit_data['operations_count']}/{self.max_per_day}"
                )
                time.sleep(total_wait)
        
        # Don't increment counters yet - wait for success confirmation
        return True

    def record_success(self):
        """Record a successful operation and reset backoff."""
        self.consecutive_failures = 0
        self.current_backoff = self.min_delay
        
        # Update rate limit data
        self.rate_limit_data["last_operation_time"] = time.time()
        self.rate_limit_data["operations_count"] += 1
        self._save_rate_limit_data()

    def record_failure(self):
        """Record a failed operation and increase backoff."""
        self.consecutive_failures += 1
        
        # Exponential backoff with maximum limit
        self.current_backoff = min(
            self.current_backoff * self.backoff_factor,
            self.max_backoff_seconds
        )
        
        self.rate_limit_data["last_operation_time"] = time.time()
        logger.warning(
            f"Operation failed for {self.name}. "
            f"Consecutive failures: {self.consecutive_failures}. "
            f"Next backoff delay: {self.current_backoff:.1f} seconds"
        )