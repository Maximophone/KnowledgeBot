import logging
import sys

# Create formatters
DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Example of how to set different levels for different components
LOGGER_LEVELS = {
    'services.file_watcher': 'DEBUG',
    'services.repeater': 'DEBUG',
    # Add more components as needed
}

def setup_logger(name: str, level: str = None) -> logging.Logger:
    """
    Creates a logger with the given name and level.
    Usage: logger = setup_logger(__name__)
    """
    logger = logging.getLogger(name)

    # Prevent logging propagation to avoid duplicate logs
    logger.propagate = False
    
    if level is None:
        # We are setting the default logging level to 'INFO'. 
        # Then, we check if the logger's name starts with any of the keys in LOGGER_LEVELS.
        # If it does, we override the default level with the specified level from LOGGER_LEVELS.
        level = 'INFO'
        for logger_name, logger_level in LOGGER_LEVELS.items():
            if name.startswith(logger_name):
                level = logger_level
                break
    logger.setLevel(getattr(logging, level.upper()))
    
    # Only add handler if logger doesn't already have handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
        logger.addHandler(handler)
    
    return logger



def configure_logging():
    """
    Configure all loggers based on LOGGER_LEVELS.
    Call this once at application startup.
    """
    for logger_name, level in LOGGER_LEVELS.items():
        setup_logger(logger_name, level)