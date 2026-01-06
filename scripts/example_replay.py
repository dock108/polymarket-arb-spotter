#!/usr/bin/env python
"""
Example script demonstrating the historical replay engine.

This script shows how to use the replay engine to replay historical
market data at different speeds and process it like live WebSocket data.

Usage:
    python scripts/example_replay.py [--db-path PATH] [--speed SPEED]

Options:
    --db-path PATH    Path to history database (default: data/market_history.db)
    --speed SPEED     Playback speed: 1 (real-time), 10 (10× fast), or jump (instant)
                     (default: jump)

Examples:
    # Replay all markets at instant speed
    python scripts/example_replay.py

    # Replay at 10× speed
    python scripts/example_replay.py --speed 10

    # Replay at real-time speed
    python scripts/example_replay.py --speed 1

    # Use custom database
    python scripts/example_replay.py --db-path /path/to/history.db
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.replay import (  # noqa: E402
    HistoricalReplayEngine,
    PlaybackSpeed,
)


def process_tick(tick: Dict[str, Any]) -> None:
    """
    Process a replayed tick like it's live data.

    This function is called for each tick during replay.
    You can replace this with your own processing logic.

    Args:
        tick: Tick data dictionary
    """
    print(
        f"[{tick['timestamp']}] Market: {tick['market_id']}, "
        f"Yes: {tick['yes_price']:.4f}, No: {tick['no_price']:.4f}, "
        f"Volume: {tick['volume']:.2f}"
    )


def main():
    """Main entry point for the example script."""
    parser = argparse.ArgumentParser(
        description="Replay historical market data",
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
        help="Playback speed: 1 (real-time), 10 (10× fast), or jump (instant) (default: jump)",
    )
    parser.add_argument(
        "--market",
        type=str,
        help="Specific market ID to replay (optional, replays all if not specified)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum ticks per market (default: 100)",
    )

    args = parser.parse_args()

    # Map speed argument to PlaybackSpeed
    if args.speed == "1":
        speed = PlaybackSpeed.REAL_TIME
        speed_name = "1× (real-time)"
    elif args.speed == "10":
        speed = PlaybackSpeed.FAST_10X
        speed_name = "10× (fast)"
    else:
        speed = PlaybackSpeed.JUMP_TO_EVENTS
        speed_name = "instant (jump-to-events)"

    # Create replay engine
    print("=" * 60)
    print("Historical Replay Engine - Example")
    print("=" * 60)
    print(f"Database: {args.db_path}")
    print(f"Speed: {speed_name}")
    print(f"Tick limit per market: {args.limit}")
    print("=" * 60)
    print()

    engine = HistoricalReplayEngine(db_path=args.db_path, speed=speed)

    # Get available markets
    markets = engine.get_available_markets()
    if not markets:
        print("❌ No historical data found in database")
        print(f"   Database path: {args.db_path}")
        print("\nTip: Run the system with history recording enabled to collect data.")
        return 1

    print(f"Found {len(markets)} market(s) with historical data:")
    for market_id in markets:
        print(f"  - {market_id}")
    print()

    # Replay markets
    if args.market:
        # Replay specific market
        if args.market not in markets:
            print(f"❌ Market '{args.market}' not found in database")
            return 1

        print(f"Replaying market: {args.market}\n")
        print("-" * 60)
        print()

        count = engine.replay_market(
            market_id=args.market,
            on_tick=process_tick,
            limit=args.limit,
        )

        print(f"\n{'-'*60}")
        print(f"✅ Replay complete: {count} ticks processed")

    else:
        # Replay all markets
        print("Replaying all markets...\n")
        print("-" * 60)
        print()

        results = engine.replay_all_markets(
            on_tick=process_tick,
            limit_per_market=args.limit,
        )

        print(f"\n{'-'*60}")
        print("✅ Replay complete:")
        for market_id, count in results.items():
            print(f"  - {market_id}: {count} ticks")
        print(f"  Total: {sum(results.values())} ticks")

    print("=" * 60)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
