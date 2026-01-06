#!/usr/bin/env python
"""
Advanced example: Using replay engine with arbitrage detection.

This script demonstrates how to use the historical replay engine to test
arbitrage detection algorithms against historical data. This allows safe
backtesting without connecting to live markets.

Usage:
    python scripts/example_replay_with_arb_detector.py [OPTIONS]

Options:
    --db-path PATH    Path to history database (default: data/market_history.db)
    --speed SPEED     Playback speed: 1, 10, or jump (default: jump)
    --market MARKET   Specific market to replay (optional)
    --limit LIMIT     Max ticks per market (default: 1000)

Example:
    # Replay all markets and detect arbitrage opportunities
    python scripts/example_replay_with_arb_detector.py

    # Replay specific market at 10× speed
    python scripts/example_replay_with_arb_detector.py --market market_123 --speed 10
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.replay import (  # noqa: E402
    HistoricalReplayEngine,
    PlaybackSpeed,
)
from app.core.arb_detector import ArbitrageDetector  # noqa: E402


class ReplayArbitrageAnalyzer:
    """
    Analyze historical data for arbitrage opportunities using replay engine.

    This class demonstrates how to integrate the replay engine with
    existing detection modules for backtesting.
    """

    def __init__(self, detector: ArbitrageDetector):
        """
        Initialize analyzer.

        Args:
            detector: ArbitrageDetector instance for finding opportunities
        """
        self.detector = detector
        self.stats = {
            "ticks_processed": 0,
            "opportunities_found": 0,
            "markets_analyzed": set(),
            "start_time": None,
            "end_time": None,
        }
        self.opportunities: List[Dict[str, Any]] = []

    def process_tick(self, tick: Dict[str, Any]) -> None:
        """
        Process a replayed tick and check for arbitrage.

        This simulates receiving live WebSocket data and processing it
        through the arbitrage detection pipeline.

        Args:
            tick: Tick data from replay engine
        """
        self.stats["ticks_processed"] += 1
        self.stats["markets_analyzed"].add(tick["market_id"])

        # Convert tick to market snapshot format expected by detector
        # In a real scenario, you would have access to full order book data
        # For this example, we create a simplified snapshot
        snapshot = {
            "id": tick["market_id"],
            "outcomes": [
                {
                    "name": "Yes",
                    "price": tick["yes_price"],
                    "volume": tick.get("volume", 0) / 2,
                },
                {
                    "name": "No",
                    "price": tick["no_price"],
                    "volume": tick.get("volume", 0) / 2,
                },
            ],
        }

        # Check for arbitrage opportunities
        opportunities = self.detector.detect_opportunities([snapshot])

        if opportunities:
            self.stats["opportunities_found"] += len(opportunities)
            for opp in opportunities:
                self.opportunities.append(
                    {
                        "timestamp": tick["timestamp"],
                        "market_id": opp.market_id,
                        "expected_return_pct": opp.expected_return_pct,
                        "expected_profit": opp.expected_profit,
                    }
                )
                print(
                    f"🎯 Arbitrage found! Market: {opp.market_id}, "
                    f"Return: {opp.expected_return_pct:.2f}%, "
                    f"Profit: ${opp.expected_profit:.2f}"
                )

    def print_summary(self) -> None:
        """Print analysis summary."""
        print("=" * 60)
        print("Analysis Summary")
        print("=" * 60)
        print(f"Ticks processed: {self.stats['ticks_processed']}")
        print(f"Markets analyzed: {len(self.stats['markets_analyzed'])}")
        print(f"Opportunities found: {self.stats['opportunities_found']}")

        if self.opportunities:
            total_profit = sum(o["expected_profit"] for o in self.opportunities)
            avg_return = (
                sum(o["expected_return_pct"] for o in self.opportunities)
                / len(self.opportunities)
            )
            print("\nProfitability:")
            print(f"  Total expected profit: ${total_profit:.2f}")
            print(f"  Average return: {avg_return:.2f}%")
            market_count = len(self.stats['markets_analyzed'])
            opp_per_market = self.stats['opportunities_found'] / market_count
            print(f"  Opportunities per market: {opp_per_market:.2f}")

        if self.stats["start_time"] and self.stats["end_time"]:
            duration = (
                self.stats["end_time"] - self.stats["start_time"]
            ).total_seconds()
            print("\nTiming:")
            print(f"  Duration: {duration:.2f}s")
            throughput = self.stats['ticks_processed'] / duration
            print(f"  Throughput: {throughput:.2f} ticks/sec")

        print("=" * 60)
        print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Replay historical data with arbitrage detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/market_history.db",
        help="Path to history database (default: data/market_history.db)",
    )
    parser.add_argument(
        "--speed",
        type=str,
        default="jump",
        choices=["1", "10", "jump"],
        help="Playback speed (default: jump)",
    )
    parser.add_argument(
        "--market",
        type=str,
        help="Specific market ID to replay (optional)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum ticks per market (default: 1000)",
    )

    args = parser.parse_args()

    # Map speed
    speed_map = {
        "1": PlaybackSpeed.REAL_TIME,
        "10": PlaybackSpeed.FAST_10X,
        "jump": PlaybackSpeed.JUMP_TO_EVENTS,
    }
    speed = speed_map[args.speed]

    print("=" * 60)
    print("Historical Replay with Arbitrage Detection")
    print("=" * 60)
    print(f"Database: {args.db_path}")
    speed_suffix = "×" if args.speed != "jump" else " (instant)"
    print(f"Speed: {args.speed}{speed_suffix}")
    if args.market:
        print(f"Market: {args.market}")
    print("=" * 60)
    print()

    # Initialize components
    detector = ArbitrageDetector()
    analyzer = ReplayArbitrageAnalyzer(detector)
    engine = HistoricalReplayEngine(db_path=args.db_path, speed=speed)

    # Check for available data
    markets = engine.get_available_markets()
    if not markets:
        print("❌ No historical data found in database")
        print(f"   Database path: {args.db_path}")
        print("\nTip: Run the system with history recording enabled to collect data.")
        return 1

    print(f"Found {len(markets)} market(s) with historical data\n")

    # Start analysis
    analyzer.stats["start_time"] = datetime.now()

    try:
        if args.market:
            # Replay specific market
            if args.market not in markets:
                print(f"❌ Market '{args.market}' not found in database")
                return 1

            print(f"Replaying market: {args.market}\n")
            count = engine.replay_market(
                market_id=args.market,
                on_tick=analyzer.process_tick,
                limit=args.limit,
            )
            print(f"\nProcessed {count} ticks from {args.market}")

        else:
            # Replay all markets
            print("Replaying all markets...\n")
            results = engine.replay_all_markets(
                on_tick=analyzer.process_tick,
                limit_per_market=args.limit,
            )
            total_ticks = sum(results.values())
            print(f"\nProcessed {total_ticks} ticks from {len(results)} market(s)")

    except KeyboardInterrupt:
        print("\n\n⚠️  Replay interrupted by user")

    finally:
        analyzer.stats["end_time"] = datetime.now()
        analyzer.print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())
