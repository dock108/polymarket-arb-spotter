#!/usr/bin/env python
"""
Production script for running the price alert watcher system.

This script:
- Loads alerts from persistent storage
- Monitors markets via WebSocket
- Sends notifications when price thresholds are crossed
- Logs triggered alerts to database
- Implements retry logic with exponential backoff
- Prints heartbeat every 60 seconds
- Handles graceful shutdown

Usage:
    python scripts/run_price_alerts.py [--log-level LEVEL]

Options:
    --log-level    Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
"""

import sys
import time
import signal
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.api_client import PolymarketAPIClient
from app.core.price_alerts import (
    PriceAlertWatcher,
    PriceAlert,
    list_alerts,
)
from app.core.notifications import send_price_alert
from app.core.logger import logger, init_db, log_price_alert_event
from app.core.config import get_config


class PriceAlertRunner:
    """
    Runner for the price alert watcher system.
    
    Manages the lifecycle of the watcher, including initialization,
    monitoring, retry logic, heartbeat, and graceful shutdown.
    """
    
    def __init__(self, log_level: str = "INFO"):
        """
        Initialize the price alert runner.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.log_level = log_level
        self.running = False
        self.watcher: Optional[PriceAlertWatcher] = None
        self.api_client: Optional[PolymarketAPIClient] = None
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 60.0  # 60 seconds
        self.retry_count = 0
        self.max_retries = 5
        self.base_backoff = 2.0  # Base backoff time in seconds
        self.config = get_config()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Configure logger
        logger.setLevel(log_level.upper())
    
    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals gracefully.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        logger.info(f"\n{signal_name} received. Shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def _alert_callback(self, alert: PriceAlert) -> None:
        """
        Callback function called when an alert is triggered.
        
        Sends notifications and logs the triggered alert to the database.
        
        Args:
            alert: PriceAlert object with triggered status
        """
        try:
            # Log the alert trigger
            logger.info(
                f"🚨 ALERT TRIGGERED: {alert.market_id} - "
                f"{alert.direction} {alert.target_price:.4f} - "
                f"Current: {alert.current_price:.4f}"
            )
            
            # Send notification (handles errors gracefully)
            success = send_price_alert(alert)
            
            if success:
                logger.info(f"✓ Notification sent for alert: {alert.market_id}")
            else:
                logger.info(f"ℹ️  Notification logged (or sending failed) for alert: {alert.market_id}")
            
            # Log the alert event to database
            try:
                alert_event = {
                    "timestamp": alert.triggered_at or datetime.now(),
                    "alert_id": f"{alert.market_id}_{alert.direction}_{alert.target_price}",
                    "market_id": alert.market_id,
                    "direction": alert.direction,
                    "target_price": alert.target_price,
                    "trigger_price": alert.current_price or 0.0,
                    "mode": "live",
                    "latency_ms": 0,  # Could be calculated if needed
                }
                log_price_alert_event(alert_event)
                logger.debug(f"✓ Alert event logged to database")
            except Exception as e:
                logger.error(f"Error logging alert event to database: {e}")
        
        except Exception as e:
            logger.error(f"Error in alert callback: {e}", exc_info=True)
    
    def _print_heartbeat(self) -> None:
        """
        Print heartbeat status message every 60 seconds.
        """
        current_time = time.time()
        if current_time - self.last_heartbeat >= self.heartbeat_interval:
            # Load current alert count
            alerts = list_alerts()
            alert_count = len(alerts)
            
            # Print heartbeat
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                f"💓 HEARTBEAT [{timestamp}] - "
                f"Monitoring {alert_count} alert(s) - "
                f"Status: {'Running' if self.running else 'Stopped'}"
            )
            
            self.last_heartbeat = current_time
    
    def _initialize_api_client(self) -> bool:
        """
        Initialize the API client and check connection health.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing Polymarket API client...")
            self.api_client = PolymarketAPIClient()
            
            # Health check
            logger.info("Performing API health check...")
            if not self.api_client.health_check():
                logger.error("API health check failed")
                return False
            
            logger.info("✓ API client initialized and healthy")
            return True
        
        except Exception as e:
            logger.error(f"Error initializing API client: {e}", exc_info=True)
            return False
    
    def _initialize_watcher(self) -> bool:
        """
        Initialize the price alert watcher.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if not self.api_client:
                logger.error("API client not initialized")
                return False
            
            # Load alerts to check if any exist
            alerts = list_alerts()
            
            if not alerts:
                logger.warning("No alerts found in storage. Add alerts before running the watcher.")
                logger.info("You can add alerts using the UI or by calling add_alert() in Python.")
                return False
            
            logger.info(f"Found {len(alerts)} alert(s) to monitor")
            
            # Display alerts
            for alert in alerts:
                logger.info(
                    f"  - {alert['market_id']}: "
                    f"{alert['direction']} {alert['target_price']:.4f}"
                )
            
            # Create watcher with callback
            logger.info("Creating price alert watcher...")
            self.watcher = PriceAlertWatcher(
                api_client=self.api_client,
                alert_cooldown=self.config.notification_throttle_seconds,
                on_alert_triggered=self._alert_callback,
            )
            
            logger.info("✓ Watcher initialized successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error initializing watcher: {e}", exc_info=True)
            return False
    
    def _calculate_backoff(self) -> float:
        """
        Calculate exponential backoff time.
        
        Returns:
            Backoff time in seconds
        """
        # Exponential backoff: base * (2 ^ retry_count)
        # Capped at 5 minutes (300 seconds)
        backoff = min(self.base_backoff * (2 ** self.retry_count), 300.0)
        return backoff
    
    def start(self) -> None:
        """
        Start the price alert watcher system.
        
        Implements retry logic with exponential backoff on failures.
        """
        logger.info("=" * 70)
        logger.info("Price Alert Watcher System")
        logger.info("=" * 70)
        logger.info(f"Log level: {self.log_level}")
        logger.info(f"Alert method: {self.config.alert_method or 'Disabled (will log only)'}")
        logger.info(f"Notification cooldown: {self.config.notification_throttle_seconds}s")
        logger.info("=" * 70)
        logger.info("")
        
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        logger.info("✓ Database initialized")
        
        # Main retry loop
        while self.retry_count < self.max_retries:
            try:
                # Initialize API client
                if not self._initialize_api_client():
                    raise RuntimeError("Failed to initialize API client")
                
                # Initialize watcher
                if not self._initialize_watcher():
                    raise RuntimeError("Failed to initialize watcher")
                
                # Start the watcher
                logger.info("Starting price alert watcher...")
                self.running = True
                self.watcher.start()
                logger.info("✓ Watcher started successfully")
                logger.info("")
                logger.info("🔍 Monitoring markets for price alerts...")
                logger.info("Press Ctrl+C to stop")
                logger.info("")
                
                # Reset retry count on successful start
                self.retry_count = 0
                
                # Monitoring loop
                while self.running:
                    self._print_heartbeat()
                    time.sleep(1.0)  # Check every second
                
                # If we exit the loop normally, break the retry loop
                break
            
            except Exception as e:
                logger.error(f"Error in watch loop: {e}", exc_info=True)
                
                # Clean up
                if self.watcher:
                    try:
                        self.watcher.stop()
                    except Exception:
                        pass
                
                self.retry_count += 1
                
                if self.retry_count >= self.max_retries:
                    logger.error(
                        f"Maximum retry attempts ({self.max_retries}) reached. "
                        "Exiting."
                    )
                    break
                
                # Calculate backoff time
                backoff = self._calculate_backoff()
                logger.warning(
                    f"Retrying in {backoff:.1f} seconds... "
                    f"(Attempt {self.retry_count}/{self.max_retries})"
                )
                time.sleep(backoff)
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("Price Alert Watcher System Stopped")
        logger.info("=" * 70)
    
    def stop(self) -> None:
        """
        Stop the price alert watcher system.
        """
        self.running = False
        
        if self.watcher:
            try:
                self.watcher.stop()
                logger.info("✓ Watcher stopped")
            except Exception as e:
                logger.error(f"Error stopping watcher: {e}")


def parse_args():
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Run the price alert watcher system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: INFO)",
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Create and start the runner
    runner = PriceAlertRunner(log_level=args.log_level)
    runner.start()


if __name__ == "__main__":
    main()
