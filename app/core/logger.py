"""
Logging configuration and utilities for the Polymarket Arbitrage Spotter.

Includes structured logging for arbitrage events using SQLite database.
"""

import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from sqlite_utils import Database


def setup_logger(
    name: str = "polymarket_arb", level: str = "INFO", log_file: Optional[str] = None
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
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
        db["arbitrage_events"].create(
            {
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
            },
            pk="id",
        )

    # Create price_alert_events table with schema if it doesn't exist
    if "price_alert_events" not in db.table_names():
        db["price_alert_events"].create(
            {
                "timestamp": str,
                "alert_id": str,
                "market_id": str,
                "direction": str,
                "target_price": float,
                "trigger_price": float,
                "mode": str,
                "latency_ms": int,
            },
            pk="id",
        )


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
    try:
        db = Database(db_path)

        # Convert timestamp to string if it's a datetime object
        event_data = data.copy()
        if hasattr(event_data.get("timestamp"), "isoformat"):
            event_data["timestamp"] = event_data["timestamp"].isoformat()

        db["arbitrage_events"].insert(event_data)

    except Exception as e:
        logger.error(f"Error logging event to database: {e}", exc_info=True)
        # Don't re-raise to allow continued processing


def _get_table_columns(db: Database, table_name: str) -> List[str]:
    """
    Get column names for a table.

    Args:
        db: Database instance
        table_name: Name of the table (must be 'arbitrage_events' or 'price_alert_events')

    Returns:
        List of column names

    Raises:
        ValueError: If table_name is not in the allowed list
    """
    # Whitelist of allowed table names to prevent SQL injection
    allowed_tables = {"arbitrage_events", "price_alert_events"}
    if table_name not in allowed_tables:
        raise ValueError(f"Invalid table name: {table_name}")

    columns = [
        col[0] for col in db.execute(f"SELECT * FROM {table_name} LIMIT 0").description
    ]
    return columns


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
    try:
        db = Database(db_path)

        # Check if table exists
        if "arbitrage_events" not in db.table_names():
            return []

        # Fetch recent entries ordered by timestamp descending using SQL
        rows = db.execute(
            "SELECT * FROM arbitrage_events ORDER BY timestamp DESC LIMIT ?", [limit]
        ).fetchall()

        # Convert to list of dictionaries
        if not rows:
            return []

        # Get column names
        columns = _get_table_columns(db, "arbitrage_events")

        return [dict(zip(columns, row)) for row in rows]

    except Exception as e:
        logger.error(f"Error fetching recent events: {e}", exc_info=True)
        return []


def log_price_alert_event(data: Dict[str, Any], db_path: str = _DB_PATH) -> None:
    """
    Log a price alert event to the database.

    Args:
        data: Dictionary containing the price alert event data with keys:
            - timestamp (datetime or str): When the alert was triggered
            - alert_id (str): Unique identifier of the alert
            - market_id (str): Unique identifier of the market
            - direction (str): Direction of the alert ("above" or "below")
            - target_price (float): Target price that triggered the alert
            - trigger_price (float): Actual price when alert was triggered
            - mode (str): Mode of operation ("mock" or "live")
            - latency_ms (int): Latency in milliseconds
        db_path: Path to the SQLite database file
    """
    try:
        db = Database(db_path)

        # Convert timestamp to string if it's a datetime object
        event_data = data.copy()
        if hasattr(event_data.get("timestamp"), "isoformat"):
            event_data["timestamp"] = event_data["timestamp"].isoformat()

        db["price_alert_events"].insert(event_data)

    except Exception as e:
        logger.error(f"Error logging price alert event to database: {e}", exc_info=True)
        # Don't re-raise to allow continued processing


def fetch_recent_price_alerts(
    limit: int = 100, db_path: str = _DB_PATH
) -> List[Dict[str, Any]]:
    """
    Fetch the most recent price alert events from the database.

    Args:
        limit: Maximum number of entries to retrieve (default: 100)
        db_path: Path to the SQLite database file

    Returns:
        List of dictionaries containing the price alert event data,
        ordered by timestamp in descending order (most recent first)
    """
    try:
        db = Database(db_path)

        # Check if table exists
        if "price_alert_events" not in db.table_names():
            return []

        # Fetch recent entries ordered by timestamp descending using SQL
        rows = db.execute(
            "SELECT * FROM price_alert_events ORDER BY timestamp DESC LIMIT ?",
            [limit],
        ).fetchall()

        # Convert to list of dictionaries
        if not rows:
            return []

        # Get column names
        columns = _get_table_columns(db, "price_alert_events")

        return [dict(zip(columns, row)) for row in rows]

    except Exception as e:
        logger.error(f"Error fetching recent price alert events: {e}", exc_info=True)
        return []


# Heartbeat monitoring
class HealthHeartbeat:
    """
    Health heartbeat monitor that logs periodic health status.

    This class runs a background thread that logs a heartbeat message
    at regular intervals to indicate the system is running and healthy.
    """

    def __init__(
        self,
        interval: int = 60,
        callback: Optional[Callable[[], Dict[str, Any]]] = None,
        logger_instance: Optional[logging.Logger] = None,
    ):
        """
        Initialize health heartbeat monitor.

        Args:
            interval: Interval in seconds between heartbeat logs (default: 60)
            callback: Optional callback function that returns health metrics dict
            logger_instance: Logger to use (defaults to module logger)
        """
        self.interval = interval
        self.callback = callback
        self.logger = logger_instance or logger
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the heartbeat monitoring thread."""
        if self._running:
            self.logger.warning("Heartbeat already running")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.logger.info(f"Health heartbeat started (interval: {self.interval}s)")

    def stop(self) -> None:
        """Stop the heartbeat monitoring thread."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=self.interval + 1)
            self._thread = None

        self.logger.info("Health heartbeat stopped")

    def _run(self) -> None:
        """Main heartbeat loop (runs in background thread)."""
        try:
            while self._running and not self._stop_event.is_set():
                try:
                    # Get health metrics from callback if provided
                    metrics = {}
                    if self.callback:
                        try:
                            metrics = self.callback()
                        except Exception as e:
                            self.logger.error(f"Error getting health metrics: {e}")

                    # Log heartbeat
                    timestamp = datetime.now().isoformat()
                    if metrics:
                        self.logger.info(
                            f"HEARTBEAT [{timestamp}] - Status: healthy - Metrics: {metrics}"
                        )
                    else:
                        self.logger.info(f"HEARTBEAT [{timestamp}] - Status: healthy")

                except Exception as e:
                    self.logger.error(f"Error in heartbeat loop: {e}", exc_info=True)

                # Wait for next heartbeat (or stop signal)
                self._stop_event.wait(timeout=self.interval)

        except Exception as e:
            self.logger.error(f"Fatal error in heartbeat thread: {e}", exc_info=True)
        finally:
            self._running = False

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


def start_heartbeat(
    interval: int = 60,
    callback: Optional[Callable[[], Dict[str, Any]]] = None,
    logger_instance: Optional[logging.Logger] = None,
) -> HealthHeartbeat:
    """
    Start a health heartbeat monitor.

    This is a convenience function to create and start a heartbeat monitor.

    Args:
        interval: Interval in seconds between heartbeat logs (default: 60)
        callback: Optional callback function that returns health metrics dict
        logger_instance: Logger to use (defaults to module logger)

    Returns:
        HealthHeartbeat instance (already started)

    Example:
        >>> heartbeat = start_heartbeat(interval=60)
        >>> # ... do work ...
        >>> heartbeat.stop()
    """
    heartbeat = HealthHeartbeat(
        interval=interval, callback=callback, logger_instance=logger_instance
    )
    heartbeat.start()
    return heartbeat
