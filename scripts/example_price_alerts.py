#!/usr/bin/env python
"""
Example script demonstrating price alert functionality.

Shows how to use the price_alerts module to watch markets and
trigger alerts when prices cross user-defined thresholds.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.price_alerts import (
    create_price_alert,
    check_price_alert,
    watch_market_price,
)


def main():
    print("=== Price Alert Example ===\n")

    # Example 1: Create an alert and check it manually
    print("Example 1: Manual alert creation and checking")
    print("-" * 50)

    # Create an alert that triggers when price goes above 0.60
    alert = create_price_alert(
        market_id="market_123",
        direction="above",
        target_price=0.60,
    )
    print(f"Created alert: {alert.alert_message}")

    # Check the alert with a price that doesn't trigger it
    result = check_price_alert(alert, 0.55)
    print(f"Price check (0.55): {result.alert_message}")
    print(f"Triggered: {result.triggered}\n")

    # Check the alert with a price that triggers it
    result = check_price_alert(alert, 0.70)
    print(f"Price check (0.70): {result.alert_message}")
    print(f"Triggered: {result.triggered}")
    print(f"Triggered at: {result.triggered_at}\n")

    # Example 2: Watch a market directly
    print("\nExample 2: Watch market with alert")
    print("-" * 50)

    # Sample market data
    market_data = {
        "id": "market_456",
        "name": "Will it rain tomorrow?",
        "outcomes": [
            {"name": "Yes", "price": 0.35},
            {"name": "No", "price": 0.65},
        ],
    }

    # Watch market with "below" alert
    alert = watch_market_price(
        market_id="market_456",
        direction="below",
        target_price=0.40,
        market_data=market_data,
    )

    print(f"Market: {market_data['name']}")
    print(f"Current Yes price: {market_data['outcomes'][0]['price']}")
    print(f"Alert: {alert.alert_message}")
    print(f"Triggered: {alert.triggered}")

    # Convert to dictionary for storage/transmission
    alert_dict = alert.to_dict()
    print(f"\nAlert as dictionary:")
    for key, value in alert_dict.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
