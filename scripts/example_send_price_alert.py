#!/usr/bin/env python
"""
Example script demonstrating the send_price_alert function.

This script shows how to use the new send_price_alert function to send
notifications when market prices cross thresholds. The function gracefully
handles disabled notifications and errors to prevent crashes in monitoring loops.
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.notifications import send_price_alert
from app.core.price_alerts import PriceAlert
from app.core.config import get_config


def main():
    """Demonstrate send_price_alert usage."""

    print("Polymarket Arbitrage Spotter - send_price_alert Example")
    print("=" * 60)

    # Get config to show current settings
    config = get_config()

    print(f"\nCurrent Configuration:")
    print(f"  Alert Method: {config.alert_method or 'None (disabled)'}")
    if config.alert_method == "telegram":
        print(
            f"  Telegram API Key: {'✓ Configured' if config.telegram_api_key else '✗ Missing'}"
        )
        print(
            f"  Telegram Chat ID: {'✓ Configured' if config.telegram_chat_id else '✗ Missing'}"
        )
    elif config.alert_method == "email":
        print(f"  Email SMTP Server: {config.email_smtp_server or '✗ Missing'}")

    print("\n" + "=" * 60)
    print("Example 1: Send alert with PriceAlert object")
    print("-" * 60)

    # Create a PriceAlert object
    price_alert = PriceAlert(
        market_id="btc_100k_by_2024",
        direction="above",
        target_price=0.65,
        current_price=0.70,
        triggered=True,
        triggered_at=datetime.now(),
        alert_message="Bitcoin market price crossed threshold!",
    )

    # Add market name for better readability
    price_alert.market_name = "Will Bitcoin hit $100K by end of 2024?"

    print(f"Market: {price_alert.market_name}")
    print(f"Current Price: ${price_alert.current_price:.4f}")
    print(f"Threshold: ${price_alert.target_price:.4f}")
    print(f"Direction: {price_alert.direction}")
    print(f"Triggered: {price_alert.triggered}")

    # Send the alert
    success = send_price_alert(price_alert)

    if success:
        print(f"\n✓ Price alert sent successfully via {config.alert_method}!")
    else:
        if not config.alert_method:
            print("\nℹ️  Alert logged (notifications disabled)")
            print("   Check logs to see the alert details")
        else:
            print(f"\n✗ Failed to send alert via {config.alert_method}")
            print("   Check logs for details")

    print("\n" + "=" * 60)
    print("Example 2: Send alert with dictionary")
    print("-" * 60)

    # Create an alert dictionary
    alert_dict = {
        "market_id": "eth_5k_by_2024",
        "market_name": "Will Ethereum reach $5K in 2024?",
        "direction": "below",
        "target_price": 0.40,
        "current_price": 0.35,
        "triggered_at": datetime.now(),
        "alert_message": "Ethereum market price dropped below threshold",
    }

    print(f"Market: {alert_dict['market_name']}")
    print(f"Current Price: ${alert_dict['current_price']:.4f}")
    print(f"Threshold: ${alert_dict['target_price']:.4f}")
    print(f"Direction: {alert_dict['direction']}")

    # Send the alert
    success = send_price_alert(alert_dict)

    if success:
        print(f"\n✓ Price alert sent successfully via {config.alert_method}!")
    else:
        if not config.alert_method:
            print("\nℹ️  Alert logged (notifications disabled)")
            print("   Check logs to see the alert details")
        else:
            print(f"\n✗ Failed to send alert via {config.alert_method}")

    print("\n" + "=" * 60)
    print("Example 3: Error handling demonstration")
    print("-" * 60)
    print("\nThe send_price_alert function gracefully handles errors")
    print("to prevent crashes in monitoring loops.")
    print()

    # Even with invalid data, it won't crash
    invalid_alert = {"market_id": "test"}
    print("Sending alert with minimal data...")
    success = send_price_alert(invalid_alert)
    print(f"Result: {success} (no exception raised)")

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print()
    print("Key Features of send_price_alert:")
    print("  ✓ Accepts both PriceAlert objects and dictionaries")
    print("  ✓ Includes market name, current price, threshold, and timestamp")
    print("  ✓ Logs alerts when notifications are disabled")
    print("  ✓ Gracefully handles errors without crashing")
    print("  ✓ Reuses existing notification infrastructure")
    print()

    if not config.alert_method:
        print("💡 Tip: Configure notification settings in .env to receive alerts")
        print("   Set ALERT_METHOD to 'telegram' or 'email' and add credentials")

    print("\n" + "=" * 60)
    print("Integration Example")
    print("-" * 60)
    print("""
from app.core.notifications import send_price_alert
from app.core.price_alerts import PriceAlertWatcher

# Callback for PriceAlertWatcher
def handle_alert(alert):
    # Send notification when price alert triggers
    # Errors won't crash the monitoring loop
    send_price_alert(alert)
    
# Create watcher with callback
watcher = PriceAlertWatcher(
    api_client=api_client,
    on_alert_triggered=handle_alert
)
watcher.start()
""")
    print("=" * 60)


if __name__ == "__main__":
    main()
