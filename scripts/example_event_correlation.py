#!/usr/bin/env python3
"""
Example script demonstrating the event correlation analyzer.

This script shows how to use the EventCorrelationAnalyzer to compute
descriptive statistics from historical market data and user labels.
"""

from datetime import datetime, timedelta
from app.core.patterns import create_analyzer
from app.core.history_store import append_ticks
from app.core.logger import save_history_label


def create_sample_data():
    """Create sample market data and labels for demonstration."""
    print("Creating sample market data...")

    base_time = datetime(2024, 1, 1, 12, 0, 0)
    ticks = []

    # Scenario 1: Whale entry at minute 10, price spikes from 0.50 to 0.70
    for i in range(120):
        if i < 10:
            price = 0.50  # Stable at 0.50
        elif i < 30:
            # Price spike (whale entry effect)
            price = 0.50 + (i - 10) * 0.01
        else:
            # Price stabilizes at 0.70
            price = 0.70

        ticks.append(
            {
                "market_id": "demo_market_1",
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "yes_price": price,
                "no_price": 1.0 - price,
                "volume": 1000.0 + i * 50,
            }
        )

    append_ticks(ticks, db_path="data/demo_history.db")

    # Label the whale entry
    save_history_label(
        {
            "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
            "market_id": "demo_market_1",
            "label_type": "whale entry",
            "notes": "Large buy order detected at 0.50",
        },
        db_path="data/demo_labels.db",
    )

    # Scenario 2: News-driven move
    base_time2 = base_time + timedelta(hours=2)
    ticks2 = []

    for i in range(120):
        if i < 5:
            price = 0.60
        elif i < 15:
            # Sharp price drop (news event)
            price = 0.60 - (i - 5) * 0.02
        else:
            # Gradual recovery
            price = 0.40 + (i - 15) * 0.001

        ticks2.append(
            {
                "market_id": "demo_market_2",
                "timestamp": (base_time2 + timedelta(minutes=i)).isoformat(),
                "yes_price": price,
                "no_price": 1.0 - price,
                "volume": 2000.0 + i * 30,
            }
        )

    append_ticks(ticks2, db_path="data/demo_history.db")

    # Label the news event
    save_history_label(
        {
            "timestamp": (base_time2 + timedelta(minutes=5)).isoformat(),
            "market_id": "demo_market_2",
            "label_type": "news-driven move",
            "notes": "Breaking news caused sharp price movement",
        },
        db_path="data/demo_labels.db",
    )

    print("Sample data created successfully!\n")


def run_analysis():
    """Run the event correlation analysis."""
    print("=" * 70)
    print("EVENT CORRELATION ANALYSIS")
    print("=" * 70)
    print()

    # Create analyzer instance
    analyzer = create_analyzer(
        history_db_path="data/demo_history.db",
        labels_db_path="data/demo_labels.db",
        resolution_window_minutes=60,
    )

    # Run analysis
    print("Running pattern analysis...")
    summary = analyzer.analyze_patterns()
    print()

    # Display results
    print("-" * 70)
    print("ANALYSIS SUMMARY")
    print("-" * 70)
    print(f"Analysis timestamp: {summary.analysis_timestamp}")
    print(f"Markets analyzed: {summary.markets_analyzed}")
    print(f"Total labels: {summary.total_labels}")
    print(f"Overall false positive rate: {summary.overall_false_positive_rate:.2%}")
    print()

    # Display pattern statistics
    if summary.pattern_stats:
        print("-" * 70)
        print("PATTERN STATISTICS")
        print("-" * 70)

        for pattern_type, stats in summary.pattern_stats.items():
            print(f"\nPattern: {pattern_type}")
            print(f"  Total occurrences: {stats.total_occurrences}")
            price_pct = stats.avg_price_move * 100
            print(
                f"  Average price move: {stats.avg_price_move:.4f} ({price_pct:.2f}%)"
            )
            print(f"  Positive outcome rate: {stats.positive_outcome_rate:.2%}")
            print(f"  False positive rate: {stats.false_positive_rate:.2%}")
            print(
                f"  Average time to resolution: {stats.avg_time_to_resolution_minutes:.1f} minutes"
            )
            print(f"  Average volume change: {stats.avg_volume_change:.0f}")
            print(f"  Sample timestamps: {', '.join(stats.sample_timestamps[:3])}")

    # Display time-to-resolution curve
    if summary.time_to_resolution_curve:
        print()
        print("-" * 70)
        print("TIME-TO-RESOLUTION CURVE")
        print("-" * 70)
        print("Time (minutes) | Resolved (%)")
        print("-" * 35)

        for time_point, resolved_pct in summary.time_to_resolution_curve:
            bar_length = int(resolved_pct / 2)  # Scale to 50 chars max
            bar = "█" * bar_length
            print(f"{time_point:>14} | {resolved_pct:>6.1f}%  {bar}")

    # Display individual signal outcomes
    if summary.signal_outcomes:
        print()
        print("-" * 70)
        print("INDIVIDUAL SIGNAL OUTCOMES")
        print("-" * 70)

        for outcome in summary.signal_outcomes[:5]:  # Show first 5
            print(f"\n{outcome.signal_type} - {outcome.market_id}")
            print(f"  Timestamp: {outcome.signal_timestamp}")
            print(f"  Initial price: {outcome.initial_price:.4f}")
            print(
                f"  Price after 5m: {outcome.price_after_5m:.4f}"
                if outcome.price_after_5m
                else "  Price after 5m: N/A"
            )
            print(
                f"  Price after 15m: {outcome.price_after_15m:.4f}"
                if outcome.price_after_15m
                else "  Price after 15m: N/A"
            )
            move_pct = outcome.max_price_move * 100
            print(f"  Max price move: {outcome.max_price_move:.4f} ({move_pct:.2f}%)")
            print(
                f"  Time to resolution: {outcome.time_to_resolution_minutes:.1f}m"
                if outcome.time_to_resolution_minutes
                else "  Time to resolution: N/A"
            )
            print(f"  Was profitable: {'Yes' if outcome.was_profitable else 'No'}")

    print()
    print("=" * 70)
    print("Analysis complete!")
    print("=" * 70)


def main():
    """Main entry point."""
    print("\nEvent Correlation Analyzer - Example Usage\n")

    # Create sample data
    create_sample_data()

    # Run analysis
    run_analysis()


if __name__ == "__main__":
    main()
