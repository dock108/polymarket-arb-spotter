"""
Example script demonstrating price alert event logging.

This script shows how to use the new price alert logging functionality
in the logger module.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from app.core.logger import (
    init_db,
    log_price_alert_event,
    fetch_recent_price_alerts,
)


def main():
    """Demonstrate price alert event logging."""

    # Initialize the database (creates tables if they don't exist)
    init_db()
    print("Database initialized")

    # Example 1: Log a price alert event with datetime object
    alert_event = {
        "timestamp": datetime.now(),
        "alert_id": "alert_12345",
        "market_id": "0x1234567890abcdef",
        "direction": "above",  # or "below"
        "target_price": 0.65,
        "trigger_price": 0.68,
        "mode": "live",  # or "mock"
        "latency_ms": 125,
    }
    log_price_alert_event(alert_event)
    print(f"Logged alert: {alert_event['alert_id']}")

    # Example 2: Log a price alert event with ISO timestamp string
    alert_event_2 = {
        "timestamp": "2024-01-05T12:30:00",
        "alert_id": "alert_67890",
        "market_id": "0xfedcba0987654321",
        "direction": "below",
        "target_price": 0.35,
        "trigger_price": 0.32,
        "mode": "live",
        "latency_ms": 98,
    }
    log_price_alert_event(alert_event_2)
    print(f"Logged alert: {alert_event_2['alert_id']}")

    # Example 3: Fetch recent price alerts
    recent_alerts = fetch_recent_price_alerts(limit=10)
    print(f"\nFetched {len(recent_alerts)} recent price alerts:")

    for alert in recent_alerts:
        print(f"  - Alert ID: {alert['alert_id']}")
        print(f"    Market: {alert['market_id']}")
        print(f"    Direction: {alert['direction']}")
        print(f"    Target: {alert['target_price']:.4f}")
        print(f"    Trigger: {alert['trigger_price']:.4f}")
        print(f"    Latency: {alert['latency_ms']}ms")
        print(f"    Timestamp: {alert['timestamp']}")
        print()


if __name__ == "__main__":
    main()
