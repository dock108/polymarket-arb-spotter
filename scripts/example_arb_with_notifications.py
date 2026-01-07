#!/usr/bin/env python
"""
Integration example: Arbitrage detector with notifications.

This script demonstrates how to integrate the notification service
with the arbitrage detector to send alerts when opportunities are found.

Usage:
    python scripts/example_arb_with_notifications.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.arb_detector import ArbitrageDetector
from app.core.notifications import send_alert
from app.core.config import get_config


def main():
    """Demonstrate arbitrage detection with notifications."""

    print("Polymarket Arbitrage Spotter - Integration Example")
    print("=" * 60)

    # Get config
    config = get_config()
    print(f"\nNotification Method: {config.alert_method or 'Disabled'}")

    # Create arbitrage detector
    detector = ArbitrageDetector(db_path=":memory:")

    # Sample market data with an arbitrage opportunity
    sample_markets = [
        {
            "id": "market_1",
            "name": "Will Bitcoin hit $100k by end of 2024?",
            "outcomes": [{"name": "yes", "price": 0.48}, {"name": "no", "price": 0.50}],
        },
        {
            "id": "market_2",
            "name": "Will Ethereum reach $5k in 2024?",
            "outcomes": [{"name": "yes", "price": 0.60}, {"name": "no", "price": 0.42}],
        },
        {
            "id": "market_3",
            "name": "Sample market with arbitrage",
            "outcomes": [{"name": "yes", "price": 0.45}, {"name": "no", "price": 0.48}],
        },
    ]

    print(f"\nAnalyzing {len(sample_markets)} markets...")
    print("-" * 60)

    alerts_sent = 0
    opportunities_found = 0

    for market in sample_markets:
        # Check for arbitrage
        alert = detector.check_arbitrage(market, fee_buffer=0.02)

        if alert.profitable:
            opportunities_found += 1
            print(f"\n✓ Arbitrage found: {market['name']}")
            print(f"  Expected profit: {alert.metrics['expected_profit_pct']:.2f}%")
            print(f"  Sum of prices: ${alert.metrics['sum_price']:.4f}")

            # Add market_id to metrics for notifications
            notification_data = alert.metrics.copy()
            notification_data["market_id"] = market["id"]

            # Send notification
            if send_alert(notification_data):
                alerts_sent += 1
                print(f"  📧 Alert sent via {config.alert_method}")
            else:
                print(f"  ℹ️  Alert not sent (method: {config.alert_method or 'None'})")
        else:
            print(f"\n✗ No arbitrage: {market['name']}")
            print(f"  Sum of prices: ${alert.metrics['sum_price']:.4f}")

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Markets analyzed: {len(sample_markets)}")
    print(f"  Opportunities found: {opportunities_found}")
    print(f"  Alerts sent: {alerts_sent}")

    if opportunities_found > 0 and alerts_sent == 0:
        print("\n💡 Tip: Configure notification settings in .env to receive alerts")
        print("   Set ALERT_METHOD to 'telegram' or 'email' and add credentials")

    print("=" * 60)

    print("\n📝 Integration Pattern:")
    print("-" * 60)
    print("from app.core.arb_detector import ArbitrageDetector")
    print("from app.core.notifications import send_alert")
    print("")
    print("# Initialize detector")
    print("detector = ArbitrageDetector()")
    print("")
    print("# Check market for arbitrage")
    print("alert = detector.check_arbitrage(market_data)")
    print("")
    print("# Send notification if profitable")
    print("if alert.profitable:")
    print("    # Add market_id for throttling")
    print("    notification_data = alert.metrics.copy()")
    print("    notification_data['market_id'] = market_data['id']")
    print("    send_alert(notification_data)")
    print("=" * 60)


if __name__ == "__main__":
    main()
