#!/usr/bin/env python3
"""
Test script to populate database with sample events for replay view testing.

This script creates sample price alerts, depth signals, and labels
to verify the timeline overlay functionality in replay_view.py.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure repo root is on sys.path so `import app...` works when run as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logger import (
    init_db,
    log_price_alert_event,
    log_depth_event,
    save_history_label,
)
from app.core.history_store import append_tick


def populate_test_data():
    """Populate database with test events for replay view."""
    print("Initializing database...")
    init_db()

    # Create a test market
    test_market_id = "test_market_timeline_overlay"
    base_time = datetime.now()

    print(f"\nCreating test data for market: {test_market_id}")

    # Create some historical ticks
    print("\n1. Creating historical price ticks...")
    for i in range(10):
        timestamp = base_time - timedelta(hours=10 - i)
        yes_price = 0.45 + (i * 0.02)  # Gradually increasing price
        no_price = 1.0 - yes_price

        append_tick(
            market_id=test_market_id,
            yes_price=yes_price,
            no_price=no_price,
            volume=1000.0 + (i * 100),  # Gradually increasing volume
            timestamp=timestamp,
        )
    print(f"   ✓ Created 10 price ticks")

    # Create price alert events
    print("\n2. Creating price alert events...")
    alerts = [
        {
            "timestamp": base_time - timedelta(hours=8),
            "alert_id": "alert_1",
            "market_id": test_market_id,
            "direction": "above",
            "target_price": 0.50,
            "trigger_price": 0.51,
            "mode": "test",
            "latency_ms": 100,
        },
        {
            "timestamp": base_time - timedelta(hours=5),
            "alert_id": "alert_2",
            "market_id": test_market_id,
            "direction": "above",
            "target_price": 0.55,
            "trigger_price": 0.56,
            "mode": "test",
            "latency_ms": 120,
        },
        {
            "timestamp": base_time - timedelta(hours=2),
            "alert_id": "alert_3",
            "market_id": test_market_id,
            "direction": "below",
            "target_price": 0.60,
            "trigger_price": 0.59,
            "mode": "test",
            "latency_ms": 95,
        },
    ]

    for alert in alerts:
        log_price_alert_event(alert)
    print(f"   ✓ Created {len(alerts)} price alerts")

    # Create depth signal events
    print("\n3. Creating depth signal events...")
    depth_events = [
        {
            "timestamp": base_time - timedelta(hours=7),
            "market_id": test_market_id,
            "metrics": {"total_depth": 450, "gap": 0.05},
            "signal_type": "thin_depth",
            "threshold_hit": "total_depth < 500",
            "mode": "test",
        },
        {
            "timestamp": base_time - timedelta(hours=4),
            "market_id": test_market_id,
            "metrics": {"total_depth": 1200, "gap": 0.12},
            "signal_type": "large_gap",
            "threshold_hit": "gap > 0.10",
            "mode": "test",
        },
        {
            "timestamp": base_time - timedelta(hours=3),
            "market_id": test_market_id,
            "metrics": {
                "total_yes_depth": 2000,
                "total_no_depth": 500,
                "imbalance": 1500,
            },
            "signal_type": "strong_imbalance",
            "threshold_hit": "imbalance > 1000",
            "mode": "test",
        },
    ]

    for event in depth_events:
        log_depth_event(event)
    print(f"   ✓ Created {len(depth_events)} depth signals")

    # Create user labels
    print("\n4. Creating user labels...")
    labels = [
        {
            "timestamp": base_time - timedelta(hours=6),
            "market_id": test_market_id,
            "label_type": "news-driven move",
            "notes": "Major news announcement caused price spike",
        },
        {
            "timestamp": base_time - timedelta(hours=3, minutes=30),
            "market_id": test_market_id,
            "label_type": "whale entry",
            "notes": "Large position entered the market",
        },
        {
            "timestamp": base_time - timedelta(hours=1),
            "market_id": test_market_id,
            "label_type": "arb collapse",
            "notes": "Arbitrage opportunity collapsed",
        },
    ]

    for label in labels:
        save_history_label(label)
    print(f"   ✓ Created {len(labels)} user labels")

    print("\n" + "=" * 60)
    print("✅ Test data population complete!")
    print("=" * 60)
    print(f"\nTest market ID: {test_market_id}")
    print(f"Time range: {base_time - timedelta(hours=10)} to {base_time}")
    print("\nTo view the data:")
    print("  1. Run: streamlit run run_live.py")
    print("  2. Navigate to 'Pattern Labeling - Replay View'")
    print(f"  3. Select market: {test_market_id}")
    print("  4. View the 'Price Chart' tab to see overlayed events")
    print("\nExpected overlay events:")
    print(f"  - {len(alerts)} Price Alerts (🔔)")
    print(f"  - {len(depth_events)} Depth Signals (📊/↔️/⚖️)")
    print(f"  - {len(labels)} User Labels (📰/🐋/📉)")
    print(f"  - Total: {len(alerts) + len(depth_events) + len(labels)} events")


if __name__ == "__main__":
    populate_test_data()
