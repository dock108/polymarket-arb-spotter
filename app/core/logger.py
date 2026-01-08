"""
Logging configuration and utilities for the Polymarket Arbitrage Spotter.
Maintains the public API for logging and proxying to specialized storage modules.
"""

import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

# Import proxy targets from specialized modules
from app.core.event_log import (
    init_db,
    log_event,
    fetch_recent,
    log_price_alert_event,
    fetch_recent_price_alerts,
    fetch_price_alert_events,
    log_depth_event,
    fetch_recent_depth_events,
    fetch_depth_events,
    save_history_label,
    fetch_history_labels,
    delete_history_label,
    save_user_annotation,
    fetch_user_annotations,
    delete_user_annotation,
    log_wallet_alert,
    fetch_recent_wallet_alerts,
    get_annotated_metrics,
    _DB_PATH
)

def setup_logger(
    name: str = "polymarket_arb", level: str = "INFO", log_file: Optional[str] = None
) -> logging.Logger:
    """
    Setup and configure logger for the application.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Avoid adding multiple handlers if setup_logger is called multiple times
    if not logger.handlers:
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

# --- Heartbeat monitoring ---

class HealthHeartbeat:
    """
    Health heartbeat monitor that logs periodic health status.
    """

    def __init__(
        self,
        interval: int = 60,
        callback: Optional[Callable[[], Dict[str, Any]]] = None,
        logger_instance: Optional[logging.Logger] = None,
    ):
        """Initialize health heartbeat monitor."""
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
        """Main heartbeat loop."""
        try:
            while self._running and not self._stop_event.is_set():
                try:
                    metrics = {}
                    if self.callback:
                        try:
                            metrics = self.callback()
                        except Exception as e:
                            self.logger.error(f"Error getting health metrics: {e}")

                    timestamp = datetime.now().isoformat()
                    self.logger.info(f"HEARTBEAT [{timestamp}] - Status: healthy" + 
                                     (f" - Metrics: {metrics}" if metrics else ""))

                except Exception as e:
                    self.logger.error(f"Error in heartbeat loop: {e}", exc_info=True)

                self._stop_event.wait(timeout=self.interval)

        except Exception as e:
            self.logger.error(f"Fatal error in heartbeat thread: {e}", exc_info=True)
        finally:
            self._running = False

def start_heartbeat(
    interval: int = 60,
    callback: Optional[Callable[[], Dict[str, Any]]] = None,
    logger_instance: Optional[logging.Logger] = None,
) -> HealthHeartbeat:
    """Convenience function to create and start a heartbeat monitor."""
    heartbeat = HealthHeartbeat(
        interval=interval, callback=callback, logger_instance=logger_instance
    )
    heartbeat.start()
    return heartbeat
