#!/usr/bin/env python
"""
Example: Backtest alerts (dry-run simulation).

This script demonstrates how to use the backtest engine to simulate
alert detection on historical data. It pipes replay events through:
- Arbitrage detector
- Price alerts
- Depth scanner

Results are stored in the backtest_results table, showing whether
tools were early, late, or wrong.

Usage:
    python scripts/example_backtest.py [OPTIONS]

Options:
    --db-path PATH    Path to history database (default: data/market_history.db)
    --market MARKET   Specific market to backtest (optional)
    --limit LIMIT     Max ticks per market (default: 1000)

Example:
    # Backtest all markets with all strategies
    python scripts/example_backtest.py

    # Backtest specific market
    python scripts/example_backtest.py --market market_123
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.replay import BacktestEngine, create_backtest_engine  # noqa: E402
from app.core.arb_detector import ArbitrageDetector  # noqa: E402
from app.core.history_store import get_backtest_results  # noqa: E402


def print_separator(char="=", length=60):
    """Print a separator line."""
    print(char * length)


def print_results_summary(stats: Dict[str, Any], db_path: str):
    """
    Print summary of backtest results.

    Args:
        stats: Statistics dictionary from backtest run
        db_path: Path to database for querying results
    """
    print_separator()
    print("Backtest Summary")
    print_separator()
    print(f"Ticks processed: {stats['ticks_processed']}")
    print(f"Markets analyzed: {stats['markets_analyzed']}")
    print()

    # Strategy-specific results
    print("Strategy Results:")
    print(f"  Arbitrage signals: {stats['arb_signals']}")
    print(f"  Price alerts triggered: {stats['price_alerts_triggered']}")
    print(f"  Depth signals: {stats['depth_signals']}")
    print()

    # Query and display sample results from each strategy
    strategies = ["arb_detector", "price_alert", "depth_scanner"]
    for strategy in strategies:
        results = get_backtest_results(strategy=strategy, limit=5, db_path=db_path)
        if results:
            print(f"\nSample {strategy} results:")
            for result in results[:3]:  # Show first 3
                signal = result.get("signal", {})
                print(f"  • Market: {result['market_id']}")
                print(f"    Time: {result['timestamp']}")
                print(f"    Outcome: {result['simulated_outcome']}")
                if strategy == "arb_detector" and signal:
                    print(
                        f"    Return: {signal.get('expected_return_pct', 0):.2f}%, "
                        f"Profit: ${signal.get('expected_profit', 0):.2f}"
                    )
                elif strategy == "price_alert" and signal:
                    print(
                        f"    Alert: {signal.get('current_price', 0):.4f} "
                        f"{signal.get('direction', '')} {signal.get('target_price', 0):.4f}"
                    )
                elif strategy == "depth_scanner" and signal:
                    print(f"    Signal: {signal.get('signal_type', 'unknown')}")
                notes = result["notes"]
                print(f"    Notes: {notes[:60]}{'...' if len(notes) > 60 else ''}")

    print_separator()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backtest alert strategies on historical data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/market_history.db",
        help="Path to history database (default: data/market_history.db)",
    )
    parser.add_argument(
        "--market",
        type=str,
        help="Specific market ID to backtest (optional)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum ticks per market (default: 1000)",
    )

    args = parser.parse_args()

    print_separator()
    print("Backtest Engine - Alert Simulation")
    print_separator()
    print(f"Database: {args.db_path}")
    if args.market:
        print(f"Market: {args.market}")
    else:
        print("Mode: All markets")
    print(f"Tick limit: {args.limit} per market")
    print_separator()
    print()

    # Initialize backtest engine
    engine = create_backtest_engine(db_path=args.db_path)

    # Check for available data
    available_markets = engine.replay_engine.get_available_markets()
    if not available_markets:
        print("❌ No historical data found in database")
        print(f"   Database path: {args.db_path}")
        print("\nTip: Run the system with history recording enabled to collect data.")
        return 1

    print(f"Found {len(available_markets)} market(s) with historical data\n")

    # Configure strategies

    # 1. Arbitrage detector
    print("Configuring arbitrage detector...")
    arb_detector = ArbitrageDetector()
    engine.set_arb_detector(arb_detector)

    # 2. Price alerts (add some example alerts if testing all markets)
    if not args.market:
        # Add alerts for first few markets as examples
        print("Configuring price alerts...")
        for market_id in available_markets[:3]:
            engine.add_price_alert(market_id, "above", 0.70)
            engine.add_price_alert(market_id, "below", 0.30)
    else:
        # Add alerts for specific market
        print("Configuring price alerts for target market...")
        engine.add_price_alert(args.market, "above", 0.70)
        engine.add_price_alert(args.market, "below", 0.30)

    # 3. Depth scanner
    print("Configuring depth scanner...")
    depth_config = {
        "min_depth": 500.0,
        "max_gap": 0.10,
        "imbalance_ratio": 300.0,
    }
    engine.set_depth_config(depth_config)

    print()
    print("=" * 60)
    print("Running backtest...")
    print("=" * 60)
    print()

    # Run backtest
    try:
        if args.market:
            stats = engine.run_backtest(
                market_ids=[args.market], limit_per_market=args.limit
            )
        else:
            stats = engine.run_backtest(limit_per_market=args.limit)

        # Print results
        print()
        print_results_summary(stats, args.db_path)

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Backtest interrupted by user")
        print()
        print_results_summary(engine.get_summary(), args.db_path)
        return 1

    except Exception as e:
        print(f"\n❌ Error during backtest: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
