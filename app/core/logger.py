"""
Logging configuration and utilities for the Polymarket Arbitrage Spotter.

TODO: Implement structured logging
TODO: Add log rotation
TODO: Add different log handlers (file, console, remote)
TODO: Add log levels per module
TODO: Implement performance logging
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "polymarket_arb",
    level: str = "INFO",
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Setup and configure logger for the application.
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        
    Returns:
        Configured logger instance
        
    TODO: Add JSON formatting for structured logs
    TODO: Add context managers for log contexts
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(console_format)
        logger.addHandler(file_handler)
    
    return logger


# Default logger instance
logger = setup_logger()
