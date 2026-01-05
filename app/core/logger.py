"""
Logging configuration and utilities for the Polymarket Arbitrage Spotter.

Includes structured logging for arbitrage events using SQLite database.

TODO: Add log rotation
TODO: Add different log handlers (file, console, remote)
TODO: Add log levels per module
TODO: Implement performance logging
"""

import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlite_utils import Database


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


# Database path for arbitrage event logging
_DB_PATH = "data/arb_logs.sqlite"


def init_db(db_path: str = _DB_PATH) -> None:
    """
    Initialize the SQLite database schema for arbitrage event logging.
    
    Creates the arbitrage_events table with the following schema:
    - timestamp (datetime): When the arbitrage happened
    - market_id (string): Unique identifier of the market
    - market_name (string): Name of the market
    - yes_price (float): Price for the 'yes' option
    - no_price (float): Price for the 'no' option
    - sum (float): Sum of prices
    - expected_profit_pct (float): Expected profit percentage
    - mode (string): Mode of operation ("mock" or "live")
    - decision (string): Decision made ("alerted" or "ignored")
    - mock_result (string | null): Result of the mock trade
    - failure_reason (string | null): Reason for any failure
    - latency_ms (integer): Latency in milliseconds
    
    Args:
        db_path: Path to the SQLite database file
    """
    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    db = Database(db_path)
    
    # Create table with schema if it doesn't exist
    if "arbitrage_events" not in db.table_names():
        db["arbitrage_events"].create({
            "timestamp": str,
            "market_id": str,
            "market_name": str,
            "yes_price": float,
            "no_price": float,
            "sum": float,
            "expected_profit_pct": float,
            "mode": str,
            "decision": str,
            "mock_result": str,
            "failure_reason": str,
            "latency_ms": int,
        }, pk="id")


def log_event(data: Dict[str, Any], db_path: str = _DB_PATH) -> None:
    """
    Log an arbitrage event to the database.
    
    Args:
        data: Dictionary containing the arbitrage event data with keys:
            - timestamp (datetime or str): When the arbitrage happened
            - market_id (str): Unique identifier of the market
            - market_name (str): Name of the market
            - yes_price (float): Price for the 'yes' option
            - no_price (float): Price for the 'no' option
            - sum (float): Sum of prices
            - expected_profit_pct (float): Expected profit percentage
            - mode (str): Mode of operation ("mock" or "live")
            - decision (str): Decision made ("alerted" or "ignored")
            - mock_result (str | None): Result of the mock trade
            - failure_reason (str | None): Reason for any failure
            - latency_ms (int): Latency in milliseconds
        db_path: Path to the SQLite database file
    """
    db = Database(db_path)
    
    # Convert timestamp to string if it's a datetime object
    event_data = data.copy()
    if hasattr(event_data.get("timestamp"), "isoformat"):
        event_data["timestamp"] = event_data["timestamp"].isoformat()
    
    db["arbitrage_events"].insert(event_data)


def fetch_recent(limit: int = 100, db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """
    Fetch the most recent arbitrage events from the database.
    
    Args:
        limit: Maximum number of entries to retrieve (default: 100)
        db_path: Path to the SQLite database file
        
    Returns:
        List of dictionaries containing the arbitrage event data,
        ordered by timestamp in descending order (most recent first)
    """
    db = Database(db_path)
    
    # Check if table exists
    if "arbitrage_events" not in db.table_names():
        return []
    
    # Fetch recent entries ordered by timestamp descending using SQL
    rows = db.execute(
        "SELECT * FROM arbitrage_events ORDER BY timestamp DESC LIMIT ?",
        [limit]
    ).fetchall()
    
    # Convert to list of dictionaries
    if not rows:
        return []
    
    # Get column names
    columns = [col[0] for col in db.execute(
        "SELECT * FROM arbitrage_events LIMIT 0"
    ).description]
    
    return [dict(zip(columns, row)) for row in rows]
