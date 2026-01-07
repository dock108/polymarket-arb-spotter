#!/usr/bin/env python3
"""
Example script demonstrating the interesting moments finder.

This script shows how to use the InterestingMomentsFinder to automatically
detect timestamps that are likely worth reviewing during analysis.
"""

from datetime import datetime, timedelta
from app.core.patterns import create_moments_finder
from app.core.history_store import append_ticks
from app.core.logger import save_history_label


def create_sample_data():
    """Create sample market data with various interesting moments."""
    print("Creating sample market data with interesting moments...")

    base_time = datetime(2024, 1, 1, 12, 0, 0)

    # Scenario 1: Sudden price acceleration
    print("  - Creating price acceleration scenario...")
    ticks1 = []
    for i in range(120):
        if i < 30:
            price = 0.50  # Stable
        elif i < 40:
            # Sudden spike (whale entry)
            price = 0.50 + (i - 30) * 0.015
        else:
            price = 0.65  # New stable level

        ticks1.append(
            {
                "market_id": "market_price_spike",
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "yes_price": price,
                "no_price": 1.0 - price,
                "volume": 1000.0,
            }
        )

    append_ticks(ticks1, db_path="data/demo_moments_history.db")

    # Label for market discovery
    save_history_label(
        {
            "timestamp": (base_time + timedelta(minutes=30)).isoformat(),
            "market_id": "market_price_spike",
            "label_type": "whale entry",
            "notes": "Large buy detected",
        },
        db_path="data/demo_moments_labels.db",
    )

    # Scenario 2: Volume spike
    print("  - Creating volume spike scenario...")
    ticks2 = []
    base_time2 = base_time + timedelta(hours=2)
    for i in range(90):
        if i == 45:
            volume = 8000.0  # Sudden volume spike
        else:
            volume = 1000.0

        ticks2.append(
            {
                "market_id": "market_volume_spike",
                "timestamp": (base_time2 + timedelta(minutes=i)).isoformat(),
                "yes_price": 0.50,
                "no_price": 0.50,
                "volume": volume,
            }
        )

    append_ticks(ticks2, db_path="data/demo_moments_history.db")

    save_history_label(
        {
            "timestamp": (base_time2 + timedelta(minutes=45)).isoformat(),
            "market_id": "market_volume_spike",
            "label_type": "volume anomaly",
            "notes": "Unusual trading volume",
        },
        db_path="data/demo_moments_labels.db",
    )

    # Scenario 3: Imbalance reversal
    print("  - Creating imbalance reversal scenario...")
    ticks3 = []
    base_time3 = base_time + timedelta(hours=4)
    for i in range(90):
        if i < 30:
            price = 0.75  # Heavy yes
        elif i < 45:
            # Reversal
            price = 0.75 - (i - 30) * 0.03
        else:
            price = 0.30  # Heavy no

        ticks3.append(
            {
                "market_id": "market_reversal",
                "timestamp": (base_time3 + timedelta(minutes=i)).isoformat(),
                "yes_price": price,
                "no_price": 1.0 - price,
                "volume": 1500.0,
            }
        )

    append_ticks(ticks3, db_path="data/demo_moments_history.db")

    save_history_label(
        {
            "timestamp": (base_time3 + timedelta(minutes=30)).isoformat(),
            "market_id": "market_reversal",
            "label_type": "news-driven move",
            "notes": "Breaking news reversed sentiment",
        },
        db_path="data/demo_moments_labels.db",
    )

    # Scenario 4: Alert cluster
    print("  - Creating alert cluster scenario...")
    ticks4 = []
    base_time4 = base_time + timedelta(hours=6)
    for i in range(60):
        ticks4.append(
            {
                "market_id": "market_alerts",
                "timestamp": (base_time4 + timedelta(minutes=i)).isoformat(),
                "yes_price": 0.50 + (i * 0.002),
                "no_price": 0.50 - (i * 0.002),
                "volume": 1200.0,
            }
        )

    append_ticks(ticks4, db_path="data/demo_moments_history.db")

    # Create alert cluster
    for j in range(6):
        save_history_label(
            {
                "timestamp": (base_time4 + timedelta(minutes=20 + j)).isoformat(),
                "market_id": "market_alerts",
                "label_type": f"alert_{j}",
                "notes": f"Alert {j} in cluster",
            },
            db_path="data/demo_moments_labels.db",
        )

    print("Sample data created successfully!\n")


def run_interesting_moments_analysis():
    """Run the interesting moments finder."""
    print("=" * 80)
    print("INTERESTING MOMENTS FINDER - AUTOMATED REVIEW CANDIDATE DETECTION")
    print("=" * 80)
    print()

    # Create finder instance
    finder = create_moments_finder(
        history_db_path="data/demo_moments_history.db",
        labels_db_path="data/demo_moments_labels.db",
        price_acceleration_threshold=0.05,  # 5% price change threshold
        volume_spike_multiplier=3.0,  # 3x volume spike
        imbalance_threshold=0.15,  # 15% from midpoint
        alert_clustering_window_minutes=5,
        min_alert_cluster_size=3,
    )

    print("Configuration:")
    print(
        f"  - Price acceleration threshold: {finder.price_acceleration_threshold:.1%}"
    )
    print(f"  - Volume spike multiplier: {finder.volume_spike_multiplier}x")
    print(f"  - Imbalance threshold: {finder.imbalance_threshold:.1%}")
    print(
        f"  - Alert clustering window: {finder.alert_clustering_window_minutes} minutes"
    )
    print(f"  - Min alert cluster size: {finder.min_alert_cluster_size}")
    print()

    # Find interesting moments
    print("Scanning for interesting moments...")
    moments = finder.find_interesting_moments(min_severity=0.0)
    print()

    # Display results
    print("-" * 80)
    print(f"FOUND {len(moments)} INTERESTING MOMENTS")
    print("-" * 80)
    print()

    if not moments:
        print("No interesting moments found.")
        return

    # Group by type for better display
    by_type = {}
    for moment in moments:
        if moment.moment_type not in by_type:
            by_type[moment.moment_type] = []
        by_type[moment.moment_type].append(moment)

    print("SUMMARY BY TYPE:")
    print("-" * 80)
    for moment_type, type_moments in sorted(by_type.items()):
        print(f"\n{moment_type.upper().replace('_', ' ')}:")
        print(f"  Count: {len(type_moments)}")
        avg_severity = sum(m.severity for m in type_moments) / len(type_moments)
        print(f"  Average severity: {avg_severity:.2f}")

    # Display top 10 moments by severity
    print()
    print("-" * 80)
    print("TOP 10 MOMENTS (by severity):")
    print("-" * 80)

    for i, moment in enumerate(moments[:10], 1):
        print(f"\n{i}. {moment.moment_type.upper().replace('_', ' ')}")
        print(f"   Market: {moment.market_id}")
        print(f"   Timestamp: {moment.timestamp}")
        print(f"   Severity: {'█' * int(moment.severity * 20)} {moment.severity:.2f}")
        print(f"   Reason: {moment.reason}")

        if moment.metrics:
            print("   Metrics:")
            for key, value in moment.metrics.items():
                if isinstance(value, float):
                    if "ratio" in key or "multiplier" in key:
                        print(f"     - {key}: {value:.2f}x")
                    elif "price" in key or "change" in key or "distance" in key:
                        print(f"     - {key}: {value:.4f} ({value * 100:.2f}%)")
                    else:
                        print(f"     - {key}: {value:.2f}")
                else:
                    print(f"     - {key}: {value}")

    print()
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print()
    print("These timestamps are flagged as potentially interesting for manual review.")
    print(
        "They exhibit unusual patterns that may indicate significant market activity."
    )


def main():
    """Main entry point."""
    print("\nInteresting Moments Finder - Example Usage\n")

    # Create sample data
    create_sample_data()

    # Run analysis
    run_interesting_moments_analysis()

    print("\nTip: Use these interesting moments to prioritize which timestamps")
    print("     to review first during manual analysis, saving significant time!")


if __name__ == "__main__":
    main()
