#!/usr/bin/env python3
"""
Speed test script for arbitrage detection using mock data.

This script runs a performance benchmark to measure how many markets
can be analyzed per second and generates arbitrage alerts rapidly.

Usage:
    python run_mock_speed.py [--duration SECONDS] [--arb-frequency FLOAT]

Features:
    - Generates fake market snapshots with configurable arbitrage frequency
    - Detects arbitrage opportunities and triggers alerts
    - Logs all events to the database
    - Can load from or export to JSON for repeatable tests
"""

import argparse
import sys
import time
from datetime import datetime

from app.core.arb_detector import ArbitrageDetector
from app.core.config import get_config
from app.core.logger import init_db, log_event, setup_logger, start_heartbeat
from app.core.mock_data import MockDataGenerator
from app.core.simulator import Simulator

# Default log database path (can be overridden by config)
DEFAULT_LOG_DB_PATH = "data/arb_logs.sqlite"


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Run speed test for Polymarket arbitrage detection"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration of speed test in seconds (default: 60)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of markets per batch (default: 10)",
    )

    parser.add_argument(
        "--num-markets",
        type=int,
        default=1000,
        help="Total number of markets to process in batch mode (default: 1000)",
    )

    parser.add_argument(
        "--mode",
        choices=["speed", "batch", "alert-test"],
        default="speed",
        help="Test mode: speed (time-based), batch (count-based), or alert-test (rapid alerts)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )

    parser.add_argument(
        "--arb-frequency",
        type=float,
        default=0.3,
        help="Frequency of arbitrage opportunities (0.0-1.0, default: 0.3)",
    )

    parser.add_argument(
        "--load-snapshots",
        type=str,
        default=None,
        help="Path to JSON file to load snapshots from",
    )

    parser.add_argument(
        "--export-snapshots",
        type=str,
        default=None,
        help="Path to export generated snapshots to JSON",
    )

    parser.add_argument(
        "--target-alerts",
        type=int,
        default=50,
        help="Target number of alerts for alert-test mode (default: 50)",
    )

    return parser.parse_args()


def print_banner():
    """Print application banner."""
    print("=" * 70)
    print("  Polymarket Arbitrage Spotter - Speed Test")
    print("=" * 70)
    print()


def print_stats(stats: dict):
    """
    Print formatted statistics.

    Args:
        stats: Statistics dictionary
    """
    print("\n" + "=" * 70)
    print("  Test Results")
    print("=" * 70)
    print(f"  Markets Analyzed:        {stats.get('markets_analyzed', 0):,}")
    print(f"  Opportunities Found:     {stats.get('opportunities_found', 0):,}")
    print(f"  Duration:                {stats.get('duration_seconds', 0):.2f} seconds")
    print(
        f"  Throughput:              {stats.get('markets_per_second', 0):.2f} markets/sec"
    )

    if "opportunities_per_second" in stats:
        print(
            f"  Opportunities/Second:    {stats.get('opportunities_per_second', 0):.4f}"
        )

    if "alerts_triggered" in stats:
        print(f"  Alerts Triggered:        {stats.get('alerts_triggered', 0):,}")

    if "total_profit" in stats:
        print(f"  Total Expected Profit:   ${stats.get('total_profit', 0):.2f}")

    print("=" * 70)
    print()


def run_alert_test(
    generator: MockDataGenerator,
    detector: ArbitrageDetector,
    target_alerts: int,
    duration_seconds: int,
    log_db_path: str,
) -> dict:
    """
    Run rapid alert generation test.

    Creates arbitrage alerts as fast as possible to test the notification pipeline.

    Args:
        generator: MockDataGenerator instance
        detector: ArbitrageDetector instance
        target_alerts: Target number of alerts to generate
        duration_seconds: Maximum duration in seconds
        log_db_path: Path to the log database

    Returns:
        Statistics dictionary
    """
    # Initialize the log database
    init_db(log_db_path)

    stats = {
        "markets_analyzed": 0,
        "opportunities_found": 0,
        "alerts_triggered": 0,
        "total_profit": 0.0,
        "start_time": datetime.now(),
    }

    end_time = datetime.now().timestamp() + duration_seconds
    batch_size = 10

    print(f"Target: {target_alerts} alerts in {duration_seconds} seconds")
    print(f"Arbitrage frequency: {generator.arb_frequency * 100:.1f}%")
    print()

    while stats["alerts_triggered"] < target_alerts and time.time() < end_time:
        # Generate batch of snapshots
        batch = generator.generate_snapshots(batch_size)
        stats["markets_analyzed"] += len(batch)

        # Detect opportunities
        opportunities = detector.detect_opportunities(batch)
        stats["opportunities_found"] += len(opportunities)

        # Process each opportunity - trigger alert and log
        for opp in opportunities:
            # Save to detector database
            detector.save_opportunity(opp)

            # Find corresponding market data
            market = next((m for m in batch if m["id"] == opp.market_id), None)

            if market:
                yes_price = market["outcomes"][0]["price"]
                no_price = market["outcomes"][1]["price"]
                price_sum = yes_price + no_price

                # Log the arbitrage event
                start_ts = time.time()
                log_event(
                    {
                        "timestamp": datetime.now(),
                        "market_id": opp.market_id,
                        "market_name": opp.market_name,
                        "yes_price": yes_price,
                        "no_price": no_price,
                        "sum": price_sum,
                        "expected_profit_pct": opp.expected_return_pct,
                        "mode": "mock",
                        "decision": "alerted",
                        "mock_result": "success",
                        "failure_reason": None,
                        "latency_ms": int((time.time() - start_ts) * 1000),
                    },
                    db_path=log_db_path,
                )

            stats["alerts_triggered"] += 1
            stats["total_profit"] += opp.expected_profit

            # Print progress
            if stats["alerts_triggered"] % 10 == 0:
                elapsed = (datetime.now() - stats["start_time"]).total_seconds()
                rate = stats["alerts_triggered"] / elapsed if elapsed > 0 else 0
                print(
                    f"  Alerts: {stats['alerts_triggered']}/{target_alerts} "
                    f"({rate:.2f}/sec)"
                )

    stats["end_time"] = datetime.now()
    duration = (stats["end_time"] - stats["start_time"]).total_seconds()
    stats["duration_seconds"] = duration
    stats["markets_per_second"] = (
        stats["markets_analyzed"] / duration if duration > 0 else 0
    )
    stats["opportunities_per_second"] = (
        stats["opportunities_found"] / duration if duration > 0 else 0
    )
    stats["alerts_per_second"] = (
        stats["alerts_triggered"] / duration if duration > 0 else 0
    )

    return stats


def main():
    """
    Main entry point for speed test.
    """
    args = parse_arguments()

    # Setup logging
    log = setup_logger(level=args.log_level)

    print_banner()

    print(f"Configuration:")
    print(f"  Mode:                    {args.mode}")
    print(f"  Duration:                {args.duration} seconds")
    print(f"  Batch Size:              {args.batch_size}")
    print(f"  Total Markets:           {args.num_markets}")
    print(f"  Random Seed:             {args.seed}")
    print(f"  Arb Frequency:           {args.arb_frequency * 100:.1f}%")
    print(f"  Log Level:               {args.log_level}")
    if args.mode == "alert-test":
        print(f"  Target Alerts:           {args.target_alerts}")
    print()

    # Initialize components
    print("Initializing components...")
    detector = ArbitrageDetector(db_path=":memory:")  # Use in-memory DB for speed
    generator = MockDataGenerator(seed=args.seed, arb_frequency=args.arb_frequency)

    # Load snapshots from file if specified
    snapshots = None
    if args.load_snapshots:
        print(f"Loading snapshots from {args.load_snapshots}...")
        try:
            snapshots = MockDataGenerator.load_snapshots(args.load_snapshots)
            print(f"  Loaded {len(snapshots)} snapshots")
        except FileNotFoundError:
            print(f"  Warning: File not found, will generate new snapshots")

    # Export snapshots if specified
    if args.export_snapshots:
        print(f"Exporting snapshots to {args.export_snapshots}...")
        export_path = generator.export_snapshots(
            count=args.num_markets, filepath=args.export_snapshots
        )
        print(f"  Exported to {export_path}")

    simulator = Simulator(detector=detector, data_generator=generator)

    print("Starting speed test...\n")

    start_time = datetime.now()

    # Get log database path from config or use default
    try:
        config = get_config()
        log_db_path = config.log_db_path
    except Exception:
        log_db_path = DEFAULT_LOG_DB_PATH

    # Start health heartbeat monitor
    heartbeat = start_heartbeat(
        interval=60, callback=lambda: {"mode": args.mode, "status": "running"}
    )

    try:
        if args.mode == "speed":
            # Time-based test
            stats = simulator.run_speed_test(duration_seconds=args.duration)
        elif args.mode == "alert-test":
            # Rapid alert generation test
            stats = run_alert_test(
                generator=generator,
                detector=detector,
                target_alerts=args.target_alerts,
                duration_seconds=args.duration,
                log_db_path=log_db_path,
            )
        else:
            # Batch-based test
            stats = simulator.run_batch_simulation(
                num_markets=args.num_markets, batch_size=args.batch_size
            )

        # Print results
        print_stats(stats)

        # Generate and print report
        print("\nDetailed Report:")
        print("-" * 70)
        print(simulator.generate_report())
        print()

        # Success message for alert-test mode
        if args.mode == "alert-test":
            alerts = stats.get("alerts_triggered", 0)
            duration = stats.get("duration_seconds", 0)
            if alerts >= args.target_alerts:
                print(f"SUCCESS: Generated {alerts} alerts in {duration:.2f} seconds")
            else:
                print(
                    f"WARNING: Only generated {alerts}/{args.target_alerts} alerts "
                    f"in {duration:.2f} seconds"
                )

        # Success
        log.info("Speed test completed successfully")
        return 0

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        log.warning("Speed test interrupted")
        return 1

    except Exception as e:
        print(f"\n\nError during speed test: {e}")
        log.error(f"Speed test failed: {e}", exc_info=True)
        return 1

    finally:
        # Stop heartbeat monitor
        heartbeat.stop()


if __name__ == "__main__":
    sys.exit(main())
