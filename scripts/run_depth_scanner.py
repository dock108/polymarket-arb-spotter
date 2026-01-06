#!/usr/bin/env python
"""
Production script for running the depth scanner system.

This script:
- Loads watched markets from depth_config.json
- Monitors markets by periodically fetching order books
- Analyzes depth metrics (thin depth, large gaps, imbalances)
- Sends notifications when depth signals are triggered
- Logs depth events to database
- Implements deduplication to avoid repeated alerts
- Implements retry logic with exponential backoff
- Prints heartbeat every 60 seconds
- Handles graceful shutdown

Usage:
    python scripts/run_depth_scanner.py [OPTIONS]

Options:
    --poll-interval SECONDS    Polling interval (default: 30)
    --duration SECONDS         Duration to run (default: run forever)
    --log-level LEVEL          Set logging level (DEBUG, INFO, WARNING, ERROR)
    --config-path PATH         Path to depth config file

Example:
    # Run with default settings
    python scripts/run_depth_scanner.py

    # Run with custom poll interval
    python scripts/run_depth_scanner.py --poll-interval 60

    # Run for limited duration
    python scripts/run_depth_scanner.py --duration 300
"""

import sys
import time
import signal
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.api_client import PolymarketAPIClient
from app.core.depth_scanner import (
    load_depth_config,
    analyze_normalized_depth,
    detect_depth_signals,
    DepthSignal,
)
from app.core.notifications import send_depth_alert
from app.core.logger import logger, init_db, log_depth_event
from app.core.config import get_config


class DepthScannerRunner:
    """
    Runner for the depth scanner system.

    Manages the lifecycle of the depth scanner, including initialization,
    monitoring, signal deduplication, retry logic, heartbeat, and graceful shutdown.
    """

    # Class constants
    MAX_BACKOFF_SECONDS = 300.0  # 5 minutes maximum backoff
    DEDUPE_WINDOW_SECONDS = 300  # 5 minutes deduplication window

    def __init__(
        self,
        poll_interval: int = 30,
        duration: Optional[int] = None,
        log_level: str = "INFO",
        config_path: Optional[str] = None,
    ):
        """
        Initialize the depth scanner runner.

        Args:
            poll_interval: Polling interval in seconds (default: 30)
            duration: Duration to run in seconds (default: None = run forever)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            config_path: Path to depth config file (default: None uses default path)
        """
        self.poll_interval = poll_interval
        self.duration = duration
        self.log_level = log_level
        self.config_path = config_path
        self.running = False
        self.api_client: Optional[PolymarketAPIClient] = None
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 60.0  # 60 seconds
        self.retry_count = 0
        self.max_retries = 5
        self.base_backoff = 2.0  # Base backoff time in seconds
        self.config = get_config()

        # Deduplication tracking: maps signal hash -> last triggered timestamp
        self._signal_dedupe: Dict[str, datetime] = {}

        # Statistics tracking
        self.stats = {
            "start_time": None,
            "markets_scanned": 0,
            "signals_detected": 0,
            "alerts_sent": 0,
            "alerts_deduplicated": 0,
            "errors": 0,
        }

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

    def _compute_signal_hash(self, market_id: str, signal: DepthSignal) -> str:
        """
        Compute a unique hash for deduplication.

        Args:
            market_id: Market identifier
            signal: DepthSignal object

        Returns:
            Hash string for the signal (128 bits / 32 hex characters)
        """
        # Create a unique key based on market_id and signal_type
        key = f"{market_id}|{signal.signal_type}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def _is_signal_duplicate(self, market_id: str, signal: DepthSignal) -> bool:
        """
        Check if a signal is a duplicate (already sent recently).

        Args:
            market_id: Market identifier
            signal: DepthSignal object

        Returns:
            True if the signal is a duplicate, False otherwise
        """
        signal_hash = self._compute_signal_hash(market_id, signal)

        if signal_hash not in self._signal_dedupe:
            return False

        last_triggered = self._signal_dedupe[signal_hash]
        elapsed = (datetime.now() - last_triggered).total_seconds()

        return elapsed < self.DEDUPE_WINDOW_SECONDS

    def _mark_signal_sent(self, market_id: str, signal: DepthSignal) -> None:
        """
        Mark a signal as sent for deduplication.

        Args:
            market_id: Market identifier
            signal: DepthSignal object
        """
        signal_hash = self._compute_signal_hash(market_id, signal)
        self._signal_dedupe[signal_hash] = datetime.now()

    def _cleanup_stale_dedupe_entries(self) -> None:
        """
        Remove stale deduplication entries older than the window.
        """
        now = datetime.now()
        stale_keys = [
            key
            for key, timestamp in self._signal_dedupe.items()
            if (now - timestamp).total_seconds() > self.DEDUPE_WINDOW_SECONDS * 2
        ]
        for key in stale_keys:
            del self._signal_dedupe[key]

    def _print_heartbeat(self) -> None:
        """
        Print heartbeat status message every 60 seconds.
        """
        current_time = time.time()
        if current_time - self.last_heartbeat >= self.heartbeat_interval:
            # Load current config for market count
            depth_config = load_depth_config(self.config_path)
            market_count = len(depth_config.get("markets_to_watch", []))

            # Print heartbeat
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                f"💓 HEARTBEAT [{timestamp}] - "
                f"Watching {market_count} market(s) - "
                f"Scanned: {self.stats['markets_scanned']} - "
                f"Signals: {self.stats['signals_detected']} - "
                f"Alerts: {self.stats['alerts_sent']} - "
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

    def _calculate_backoff(self) -> float:
        """
        Calculate exponential backoff time.

        Returns:
            Backoff time in seconds
        """
        # Exponential backoff: base * (2 ^ retry_count)
        # Capped at MAX_BACKOFF_SECONDS (5 minutes)
        backoff = min(
            self.base_backoff * (2**self.retry_count), self.MAX_BACKOFF_SECONDS
        )
        return backoff

    def _process_market(self, market_id: str, depth_config: Dict[str, Any]) -> None:
        """
        Process a single market for depth analysis.

        Args:
            market_id: Market identifier to process
            depth_config: Depth configuration dictionary
        """
        try:
            logger.debug(f"Fetching orderbook for market: {market_id}")

            # Fetch orderbook
            orderbook = self.api_client.fetch_orderbook(market_id, depth=10)

            if orderbook is None:
                logger.warning(f"Could not fetch orderbook for market: {market_id}")
                return

            self.stats["markets_scanned"] += 1

            # Analyze depth using normalized orderbook data
            yes_bids = orderbook.yes_bids or []
            yes_asks = orderbook.yes_asks or []
            no_bids = orderbook.no_bids or []
            no_asks = orderbook.no_asks or []

            metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)

            # Detect signals
            signals = detect_depth_signals(metrics, depth_config)

            if not signals:
                logger.debug(f"No signals detected for market: {market_id}")
                return

            # Process each signal
            for depth_signal in signals:
                self.stats["signals_detected"] += 1

                # Check deduplication
                if self._is_signal_duplicate(market_id, depth_signal):
                    logger.debug(
                        f"Signal deduplicated: {depth_signal.signal_type} for {market_id}"
                    )
                    self.stats["alerts_deduplicated"] += 1
                    continue

                # Log signal detection
                logger.info(
                    f"🚨 SIGNAL DETECTED: {depth_signal.signal_type} for market {market_id}"
                )
                logger.info(f"   Reason: {depth_signal.reason}")

                # Send notification
                signal_dict = depth_signal.to_dict()
                signal_dict["market_id"] = market_id

                success = send_depth_alert(signal_dict)

                if success:
                    logger.info(f"✓ Notification sent for {depth_signal.signal_type}")
                    self.stats["alerts_sent"] += 1
                else:
                    logger.info(
                        f"ℹ️  Notification logged (or notifications disabled) "
                        f"for {depth_signal.signal_type}"
                    )

                # Mark signal as sent for deduplication
                self._mark_signal_sent(market_id, depth_signal)

                # Log depth event to database
                try:
                    event_data = {
                        "timestamp": datetime.now(),
                        "market_id": market_id,
                        "metrics": metrics,
                        "signal_type": depth_signal.signal_type,
                        "threshold_hit": depth_signal.reason,
                        "mode": "live",
                    }
                    log_depth_event(event_data)
                    logger.debug("✓ Depth event logged to database")
                except Exception as e:
                    logger.error(f"Error logging depth event to database: {e}")

        except Exception as e:
            logger.error(f"Error processing market {market_id}: {e}", exc_info=True)
            self.stats["errors"] += 1

    def _run_scan_iteration(self) -> None:
        """
        Run a single scan iteration over all watched markets.
        """
        # Load depth config
        depth_config = load_depth_config(self.config_path)
        markets_to_watch = depth_config.get("markets_to_watch", [])

        if not markets_to_watch:
            logger.warning(
                "No markets configured in depth_config.json. "
                "Add market IDs to 'markets_to_watch' list."
            )
            return

        logger.info(f"Scanning {len(markets_to_watch)} market(s)...")

        for market_id in markets_to_watch:
            if not self.running:
                break
            self._process_market(market_id, depth_config)

        # Cleanup stale deduplication entries periodically
        self._cleanup_stale_dedupe_entries()

    def start(self) -> None:
        """
        Start the depth scanner system.

        Implements retry logic with exponential backoff on failures.
        """
        logger.info("=" * 70)
        logger.info("Depth Scanner System")
        logger.info("=" * 70)
        logger.info(f"Log level: {self.log_level}")
        logger.info(f"Poll interval: {self.poll_interval}s")
        logger.info(
            f"Alert method: {self.config.alert_method or 'Disabled (will log only)'}"
        )
        logger.info(f"Deduplication window: {self.DEDUPE_WINDOW_SECONDS}s")
        if self.duration:
            logger.info(f"Duration: {self.duration}s")
        else:
            logger.info("Duration: Indefinite (Ctrl+C to stop)")
        logger.info("=" * 70)
        logger.info("")

        # Initialize database
        logger.info("Initializing database...")
        init_db()
        logger.info("✓ Database initialized")

        # Load and display watched markets
        depth_config = load_depth_config(self.config_path)
        markets_to_watch = depth_config.get("markets_to_watch", [])

        if not markets_to_watch:
            logger.warning(
                "No markets configured to watch. Add market IDs to "
                "'markets_to_watch' in data/depth_config.json"
            )
            logger.info('Example: {"markets_to_watch": ["token_id_1", "token_id_2"]}')
            return

        logger.info(f"Found {len(markets_to_watch)} market(s) to watch:")
        for market_id in markets_to_watch:
            logger.info(f"  - {market_id}")

        logger.info("Depth thresholds from config:")
        logger.info(f"  - min_depth: {depth_config.get('min_depth', 500.0)}")
        logger.info(f"  - max_gap: {depth_config.get('max_gap', 0.10)}")
        logger.info(
            f"  - imbalance_ratio: {depth_config.get('imbalance_ratio', 300.0)}"
        )
        logger.info("")

        # Main retry loop
        while self.retry_count < self.max_retries:
            try:
                # Initialize API client
                if not self._initialize_api_client():
                    raise RuntimeError("Failed to initialize API client")

                # Set running flag and track start time
                self.running = True
                self.stats["start_time"] = datetime.now()
                self.retry_count = 0  # Reset retry count on successful start

                logger.info("✓ Depth scanner started successfully")
                logger.info("")
                logger.info("🔍 Monitoring markets for depth signals...")
                logger.info("Press Ctrl+C to stop")
                logger.info("")

                # Calculate end time if duration is specified
                end_time = None
                if self.duration:
                    end_time = datetime.now() + timedelta(seconds=self.duration)

                # Main monitoring loop
                while self.running:
                    # Check if we should stop
                    if end_time and datetime.now() >= end_time:
                        logger.info("Duration limit reached")
                        break

                    # Run scan iteration
                    self._run_scan_iteration()

                    # Print heartbeat
                    self._print_heartbeat()

                    # Sleep until next iteration
                    if self.running:
                        time.sleep(self.poll_interval)

                # If we exit the loop normally, break the retry loop
                break

            except Exception as e:
                logger.error(f"Error in scan loop: {e}", exc_info=True)

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

        # Print final summary
        self._print_summary()

        logger.info("")
        logger.info("=" * 70)
        logger.info("Depth Scanner System Stopped")
        logger.info("=" * 70)

    def _print_summary(self) -> None:
        """
        Print final summary statistics.
        """
        if not self.stats["start_time"]:
            return

        elapsed = (datetime.now() - self.stats["start_time"]).total_seconds()

        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 DEPTH SCANNER SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total Runtime:          {elapsed:.1f}s ({elapsed / 60:.1f}min)")
        logger.info(f"Markets Scanned:        {self.stats['markets_scanned']}")
        logger.info(f"Signals Detected:       {self.stats['signals_detected']}")
        logger.info(f"Alerts Sent:            {self.stats['alerts_sent']}")
        logger.info(f"Alerts Deduplicated:    {self.stats['alerts_deduplicated']}")
        logger.info(f"Errors:                 {self.stats['errors']}")

        if elapsed > 0 and self.stats["markets_scanned"] > 0:
            rate = self.stats["markets_scanned"] / elapsed
            logger.info(f"Scan Rate:              {rate:.2f} markets/sec")

        logger.info("=" * 70)

    def stop(self) -> None:
        """
        Stop the depth scanner system.
        """
        self.running = False
        logger.info("✓ Depth scanner stopped")


def parse_args():
    """
    Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Run the depth scanner system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (30s poll interval)
  python scripts/run_depth_scanner.py

  # Run with custom poll interval
  python scripts/run_depth_scanner.py --poll-interval 60

  # Run for 5 minutes
  python scripts/run_depth_scanner.py --duration 300

  # Run with custom config path
  python scripts/run_depth_scanner.py --config-path /path/to/config.json

Note: Configure markets to watch in data/depth_config.json
        """,
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Polling interval in seconds (default: 30)",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Duration to run in seconds (default: run forever)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: INFO)",
    )

    parser.add_argument(
        "--config-path",
        type=str,
        default=None,
        help="Path to depth config file (default: data/depth_config.json)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Create and start the runner
    runner = DepthScannerRunner(
        poll_interval=args.poll_interval,
        duration=args.duration,
        log_level=args.log_level,
        config_path=args.config_path,
    )
    runner.start()


if __name__ == "__main__":
    main()
