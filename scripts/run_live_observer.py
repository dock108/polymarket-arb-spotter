#!/usr/bin/env python3
"""
Live observer script for Polymarket arbitrage opportunities (CLI mode).

This script runs a command-line observer that:
1. Connects to Polymarket streams (via WebSocket or API polling)
2. Detects arbitrage opportunities in real-time
3. Sends alerts via configured notification method
4. Runs mock simulator to estimate execution success
5. Logs everything to database
6. NEVER TRADES - detection only!

Note: For the interactive UI dashboard, use `streamlit run run_live.py` instead.

Usage:
    python scripts/run_live_observer.py [OPTIONS]

Options:
    --mode {stream,poll}          Connection mode (default: poll)
    --poll-interval SECONDS       Polling interval for poll mode (default: 30)
    --duration SECONDS            Duration to run (default: run forever)
    --max-markets N               Maximum markets to monitor (default: 100)
    --mock-trades                 Enable mock trade simulation (default: True)
    --no-mock-trades              Disable mock trade simulation
    --log-level LEVEL             Logging level (default: INFO)

Example:
    # Run with polling (default, safe)
    python scripts/run_live.py --poll-interval 60

    # Run with WebSocket streaming (requires websocket-client)
    python scripts/run_live.py --mode stream

    # Run for limited duration with mock trades disabled
    python scripts/run_live.py --duration 300 --no-mock-trades
"""

import os
import sys
import argparse
import signal
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.api_client import PolymarketAPIClient
from app.core.arb_detector import ArbitrageDetector, ArbitrageOpportunity
from app.core.notifications import send_alert
from app.core.simulator import MockTradeExecutor
from app.core.logger import logger, init_db, log_event
from app.core.config import get_config


class LiveObserver:
    """
    Live observer for Polymarket arbitrage opportunities.

    This class orchestrates the detection, alerting, simulation, and logging
    of arbitrage opportunities in real-time.

    WARNING: This is a DETECTION-ONLY system. It NEVER executes actual trades.
    """

    def __init__(
        self,
        mode: str = "poll",
        poll_interval: int = 30,
        duration: Optional[int] = None,
        max_markets: int = 100,
        enable_mock_trades: bool = True,
        log_level: str = "INFO",
    ):
        """
        Initialize the live observer.

        Args:
            mode: Connection mode - "stream" (WebSocket) or "poll" (API polling)
            poll_interval: Polling interval in seconds (for poll mode)
            duration: Duration to run in seconds (None = run forever)
            max_markets: Maximum number of markets to monitor
            enable_mock_trades: Whether to run mock trade simulations
            log_level: Logging level
        """
        self.mode = mode
        self.poll_interval = poll_interval
        self.duration = duration
        self.max_markets = max_markets
        self.enable_mock_trades = enable_mock_trades

        # Load configuration
        self.config = get_config()

        # Initialize components
        self.api_client = PolymarketAPIClient()
        self.detector = ArbitrageDetector(db_path=self.config.db_path)
        # MockTradeExecutor uses default parameters intentionally for realistic simulation
        # (fee_rate=0.02, price_volatility=0.02, depth_variability=0.5)
        self.mock_executor = MockTradeExecutor() if enable_mock_trades else None

        # Initialize database for event logging
        init_db(db_path=self.config.log_db_path)

        # Statistics tracking
        self.stats = {
            "start_time": None,
            "markets_analyzed": 0,
            "opportunities_found": 0,
            "alerts_sent": 0,
            "mock_trades_executed": 0,
            "mock_trades_successful": 0,
            "running": False,
        }

        # Graceful shutdown flag
        self._shutdown_requested = False

        logger.info(f"LiveObserver initialized in {mode} mode")
        logger.info(f"Alert method: {self.config.alert_method or 'Disabled'}")
        logger.info(f"Mock trades: {'Enabled' if enable_mock_trades else 'Disabled'}")
        logger.info(f"Database: {self.config.log_db_path}")

    def start(self):
        """Start the live observer."""
        self._print_banner()

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        self.stats["start_time"] = datetime.now()
        self.stats["running"] = True

        logger.info("Starting live observer...")

        try:
            if self.mode == "stream":
                self._run_stream_mode()
            elif self.mode == "poll":
                self._run_poll_mode()
            else:
                logger.error(f"Invalid mode: {self.mode}")
                sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
        finally:
            self._print_summary()
            self.stats["running"] = False

    def _run_poll_mode(self):
        """Run in polling mode - periodically fetch markets from API."""
        logger.info(f"Starting poll mode with {self.poll_interval}s interval")

        end_time = None
        if self.duration:
            end_time = datetime.now() + timedelta(seconds=self.duration)
            logger.info(f"Will run for {self.duration} seconds")
        else:
            logger.info("Running indefinitely (Ctrl+C to stop)")

        iteration = 0
        while not self._shutdown_requested:
            iteration += 1

            # Check if we should stop
            if end_time and datetime.now() >= end_time:
                logger.info("Duration limit reached")
                break

            logger.info(f"\n{'='*70}")
            logger.info(
                f"Iteration {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info(f"{'='*70}")

            # Fetch markets from API
            try:
                markets = self.api_client.fetch_markets(
                    limit=min(self.max_markets, 100), active_only=True
                )

                if not markets:
                    logger.warning("No markets fetched from API")
                else:
                    logger.info(f"Fetched {len(markets)} markets")
                    self._process_markets(markets)

            except Exception as e:
                logger.error(f"Error fetching markets: {e}")

            # Print periodic summary
            self._print_periodic_summary()

            # Sleep until next iteration (unless shutdown requested)
            if not self._shutdown_requested:
                logger.info(f"Sleeping for {self.poll_interval}s...")
                time.sleep(self.poll_interval)

    def _run_stream_mode(self):
        """Run in streaming mode - subscribe to WebSocket updates."""
        logger.info("Starting stream mode via WebSocket")

        # First, fetch market IDs to subscribe to
        try:
            markets = self.api_client.fetch_markets(
                limit=min(self.max_markets, 100), active_only=True
            )

            if not markets:
                logger.error("No markets available to subscribe to")
                return

            # Extract market IDs (token_ids or condition_ids)
            market_ids = []
            for market in markets:
                # Try different possible ID fields
                market_id = (
                    market.get("condition_id")
                    or market.get("token_id")
                    or market.get("id")
                )
                if market_id:
                    market_ids.append(market_id)

            if not market_ids:
                logger.error("Could not extract market IDs for streaming")
                return

            logger.info(f"Subscribing to {len(market_ids)} markets via WebSocket")

            # Stream price updates
            end_time = None
            if self.duration:
                end_time = datetime.now() + timedelta(seconds=self.duration)

            def handle_ws_error(e):
                """Handle WebSocket error with full traceback."""
                logger.error(f"WebSocket error: {e}", exc_info=True)

            for update in self.api_client.websocket_stream_prices(
                market_ids=market_ids[:50],  # Limit to 50 for WebSocket
                on_error=handle_ws_error,
            ):
                if self._shutdown_requested:
                    break

                if end_time and datetime.now() >= end_time:
                    logger.info("Duration limit reached")
                    break

                # Process update
                logger.debug(f"Received WebSocket update: {update}")
                # Note: WebSocket updates would need to be converted to market format
                # for processing - this is a simplified implementation

        except Exception as e:
            logger.error(f"Error in stream mode: {e}", exc_info=True)

    def _process_markets(self, markets: List[Dict[str, Any]]):
        """
        Process a batch of markets for arbitrage detection.

        Args:
            markets: List of market data dictionaries
        """
        for market in markets:
            if self._shutdown_requested:
                break

            self.stats["markets_analyzed"] += 1

            try:
                # Check for arbitrage opportunity
                alert = self.detector.check_arbitrage(
                    market, fee_buffer=self.config.fee_buffer_percent / 100.0
                )

                # Process if profitable
                if alert.profitable:
                    self._handle_opportunity(market, alert)

            except Exception as e:
                logger.error(
                    f"Error processing market {market.get('id', 'unknown')}: {e}"
                )

    def _handle_opportunity(self, market: Dict[str, Any], alert):
        """
        Handle a detected arbitrage opportunity.

        Args:
            market: Market data dictionary
            alert: ArbAlert from the detector
        """
        self.stats["opportunities_found"] += 1

        market_id = market.get("id", "unknown")
        market_name = market.get("name", market.get("question", "Unknown Market"))

        # Log to console
        logger.info("\n" + "*" * 70)
        logger.info("🚨 ARBITRAGE OPPORTUNITY DETECTED!")
        logger.info("*" * 70)
        logger.info(f"Market ID: {market_id}")
        logger.info(f"Market: {market_name}")
        logger.info(f"Expected Profit: {alert.metrics['expected_profit_pct']:.2f}%")
        logger.info(f"Sum of Prices: ${alert.metrics['sum_price']:.4f}")
        logger.info(f"Threshold: ${alert.metrics.get('threshold', 'N/A')}")

        prices = alert.metrics.get("prices", {}) or {}  # Handle None case
        logger.info(f"Yes Price: ${prices.get('yes_price', 0):.4f}")
        logger.info(f"No Price: ${prices.get('no_price', 0):.4f}")

        # Send alert notification
        alert_sent = False
        if self.config.alert_method:
            notification_data = alert.metrics.copy()
            notification_data["market_id"] = market_id

            try:
                if send_alert(notification_data):
                    self.stats["alerts_sent"] += 1
                    alert_sent = True
                    logger.info(f"✓ Alert sent via {self.config.alert_method}")
                else:
                    logger.info("ℹ️  Alert not sent (throttled or error)")
            except Exception as e:
                logger.error(f"Error sending alert: {e}")
        else:
            logger.info("ℹ️  Notifications disabled")

        # Run mock trade simulation
        mock_result = None
        failure_reason = None

        if self.enable_mock_trades and self.mock_executor:
            try:
                # Convert alert to ArbitrageOpportunity for simulation
                opportunity = ArbitrageOpportunity(
                    market_id=market_id,
                    market_name=market_name,
                    opportunity_type="two-way",
                    expected_profit=alert.metrics["expected_profit_pct"],
                    expected_return_pct=alert.metrics["expected_profit_pct"],
                    positions=[
                        {
                            "outcome": "yes",
                            "action": "BUY",
                            "price": prices.get("yes_price", 0),
                            "volume": market.get("volume", 10000),
                        },
                        {
                            "outcome": "no",
                            "action": "BUY",
                            "price": prices.get("no_price", 0),
                            "volume": market.get("volume", 10000),
                        },
                    ],
                    detected_at=datetime.now(),
                )

                # Execute mock trade with configurable trade amount (default $100)
                # This simulates a small trade to estimate execution feasibility
                trade_amount = (
                    self.config.max_stake
                    if hasattr(self.config, "max_stake")
                    else 100.0
                )
                execution = self.mock_executor.execute_trade(
                    opportunity, trade_amount=trade_amount
                )

                self.stats["mock_trades_executed"] += 1
                if execution.success:
                    self.stats["mock_trades_successful"] += 1

                mock_result = execution.result.value
                failure_reason = execution.failure_reason

                logger.info("\n📊 Mock Trade Simulation:")
                logger.info(f"  Result: {execution.result.value}")
                logger.info(f"  Success: {execution.success}")
                if not execution.success:
                    logger.info(f"  Failure Reason: {failure_reason}")
                logger.info(f"  Original Profit: {execution.original_profit_pct:.2f}%")
                logger.info(f"  Final Profit: {execution.final_profit_pct:.2f}%")
                logger.info(f"  Simulated Delay: {execution.simulated_delay_ms:.1f}ms")
                logger.info(f"  Price Shift: {execution.price_shift_pct*100:.2f}%")
                logger.info(
                    f"  Fill Ratio: {execution.filled_amount/execution.requested_amount*100:.1f}%"
                )

            except Exception as e:
                logger.error(f"Error in mock trade simulation: {e}")

        # Log event to database
        try:
            log_event(
                {
                    "timestamp": datetime.now(),
                    "market_id": market_id,
                    "market_name": market_name,
                    "yes_price": prices.get("yes_price", 0),
                    "no_price": prices.get("no_price", 0),
                    "sum": alert.metrics["sum_price"],
                    "expected_profit_pct": alert.metrics["expected_profit_pct"],
                    "mode": "live",
                    "decision": "alerted" if alert_sent else "logged",
                    "mock_result": mock_result,
                    "failure_reason": failure_reason,
                    "latency_ms": 0,  # Not applicable in live mode
                },
                db_path=self.config.log_db_path,
            )
        except Exception as e:
            logger.error(f"Error logging event: {e}")

        logger.info(f"{'*'*70}\n")

    def _print_banner(self):
        """Print startup banner with important warnings."""
        banner = """
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║        🎯 POLYMARKET ARBITRAGE SPOTTER - LIVE OBSERVER 🎯            ║
║                                                                      ║
║                    ⚠️  DETECTION ONLY MODE ⚠️                        ║
║                                                                      ║
║  This system DETECTS arbitrage opportunities but NEVER executes     ║
║  actual trades. It is for monitoring and analysis purposes only.    ║
║                                                                      ║
║  ⛔ NO TRADING - NO REAL MONEY INVOLVED - OBSERVATION ONLY ⛔       ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""
        print(banner)
        print(f"Mode: {self.mode.upper()}")
        print(f"Alert Method: {self.config.alert_method or 'Disabled'}")
        print(f"Mock Trades: {'Enabled' if self.enable_mock_trades else 'Disabled'}")
        print(f"Max Markets: {self.max_markets}")
        if self.mode == "poll":
            print(f"Poll Interval: {self.poll_interval}s")
        if self.duration:
            print(f"Duration: {self.duration}s")
        else:
            print("Duration: Indefinite (Ctrl+C to stop)")
        print(f"\nDatabase: {self.config.log_db_path}")
        print(f"Log File: {self.config.log_file}")
        print("=" * 70)
        print()

    def _print_periodic_summary(self):
        """Print a periodic summary of statistics."""
        elapsed = (datetime.now() - self.stats["start_time"]).total_seconds()

        print(f"\n{'─'*70}")
        print(f"📊 SUMMARY (Elapsed: {elapsed:.0f}s)")
        print(f"{'─'*70}")
        print(f"Markets Analyzed:       {self.stats['markets_analyzed']}")
        print(f"Opportunities Found:    {self.stats['opportunities_found']}")
        print(f"Alerts Sent:            {self.stats['alerts_sent']}")

        if self.enable_mock_trades:
            print(f"Mock Trades Executed:   {self.stats['mock_trades_executed']}")
            print(f"Mock Trades Successful: {self.stats['mock_trades_successful']}")
            if self.stats["mock_trades_executed"] > 0:
                success_rate = (
                    self.stats["mock_trades_successful"]
                    / self.stats["mock_trades_executed"]
                    * 100
                )
                print(f"Success Rate:           {success_rate:.1f}%")

        if elapsed > 0:
            rate = self.stats["markets_analyzed"] / elapsed
            print(f"Analysis Rate:          {rate:.2f} markets/sec")

        print(f"{'─'*70}\n")

    def _print_summary(self):
        """Print final summary at shutdown."""
        if not self.stats["start_time"]:
            return

        elapsed = (datetime.now() - self.stats["start_time"]).total_seconds()

        print("\n\n")
        print("=" * 70)
        print("🏁 LIVE OBSERVER FINAL SUMMARY")
        print("=" * 70)
        print(f"Total Runtime:          {elapsed:.1f}s ({elapsed/60:.1f}min)")
        print(f"Markets Analyzed:       {self.stats['markets_analyzed']}")
        print(f"Opportunities Found:    {self.stats['opportunities_found']}")
        print(f"Alerts Sent:            {self.stats['alerts_sent']}")

        if self.enable_mock_trades:
            print("\nMock Trade Simulation:")
            print(f"  Executed:             {self.stats['mock_trades_executed']}")
            print(f"  Successful:           {self.stats['mock_trades_successful']}")
            if self.stats["mock_trades_executed"] > 0:
                success_rate = (
                    self.stats["mock_trades_successful"]
                    / self.stats["mock_trades_executed"]
                    * 100
                )
                print(f"  Success Rate:         {success_rate:.1f}%")

        if elapsed > 0 and self.stats["markets_analyzed"] > 0:
            rate = self.stats["markets_analyzed"] / elapsed
            print("\nPerformance:")
            print(f"  Analysis Rate:        {rate:.2f} markets/sec")
            if self.stats["opportunities_found"] > 0:
                opp_rate = self.stats["opportunities_found"] / elapsed * 60
                print(f"  Opportunity Rate:     {opp_rate:.2f} per minute")

        print(f"\nDatabase: {self.config.log_db_path}")
        print("All events logged to database for review.")
        print("=" * 70)
        print("\n⛔ REMINDER: This system NEVER executes real trades. ⛔")
        print("   All detected opportunities are for monitoring only.")
        print("=" * 70 + "\n")

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal gracefully."""
        logger.info(f"\nReceived shutdown signal ({signum})")
        self._shutdown_requested = True


def main():
    """Main entry point for the live observer script."""
    parser = argparse.ArgumentParser(
        description="Live observer for Polymarket arbitrage opportunities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (poll mode, 30s interval)
  python scripts/run_live.py
  
  # Run with custom poll interval
  python scripts/run_live.py --poll-interval 60
  
  # Run for 5 minutes with alerts
  python scripts/run_live.py --duration 300
  
  # Run in stream mode (requires WebSocket)
  python scripts/run_live.py --mode stream
  
  # Run without mock trade simulation
  python scripts/run_live.py --no-mock-trades

Note: This system NEVER executes real trades. It is for detection only.
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["stream", "poll"],
        default="poll",
        help="Connection mode: stream (WebSocket) or poll (API) (default: poll)",
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Polling interval in seconds for poll mode (default: 30)",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Duration to run in seconds (default: run forever)",
    )

    parser.add_argument(
        "--max-markets",
        type=int,
        default=100,
        help="Maximum number of markets to monitor (default: 100)",
    )

    parser.add_argument(
        "--mock-trades",
        dest="enable_mock_trades",
        action="store_true",
        default=True,
        help="Enable mock trade simulation (default: enabled)",
    )

    parser.add_argument(
        "--no-mock-trades",
        dest="enable_mock_trades",
        action="store_false",
        help="Disable mock trade simulation",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Create and start observer
    observer = LiveObserver(
        mode=args.mode,
        poll_interval=args.poll_interval,
        duration=args.duration,
        max_markets=args.max_markets,
        enable_mock_trades=args.enable_mock_trades,
        log_level=args.log_level,
    )

    observer.start()

    return 0


if __name__ == "__main__":
    sys.exit(main())
