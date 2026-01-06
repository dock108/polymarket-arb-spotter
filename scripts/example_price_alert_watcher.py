#!/usr/bin/env python
"""
Example script demonstrating the PriceAlertWatcher functionality.

Shows how to:
1. Add alerts to the alert list
2. Start a watcher that subscribes to markets
3. Monitor price updates and trigger alerts
4. Handle alert callbacks
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.api_client import PolymarketAPIClient, NormalizedOrderBook
from app.core.price_alerts import (
    PriceAlertWatcher,
    PriceAlert,
    add_alert,
    list_alerts,
    remove_alert,
)


def alert_callback(alert: PriceAlert) -> None:
    """
    Callback function that's called when an alert is triggered.

    Args:
        alert: PriceAlert object with triggered status
    """
    print(f"\n🚨 ALERT TRIGGERED! 🚨")
    print(f"  Market: {alert.market_id}")
    print(f"  Direction: {alert.direction}")
    print(f"  Target: {alert.target_price:.4f}")
    print(f"  Current: {alert.current_price:.4f}")
    print(f"  Message: {alert.alert_message}")
    print(f"  Time: {alert.triggered_at}")
    print()


def main():
    print("=" * 70)
    print("Price Alert Watcher Example")
    print("=" * 70)
    print()

    # Initialize API client (read-only)
    print("Initializing API client...")
    api_client = PolymarketAPIClient()

    # Check API health
    if not api_client.health_check():
        print("❌ API health check failed. Please check your connection.")
        return

    print("✅ API is healthy\n")

    # Add some example alerts
    print("Adding example alerts...")

    # Example 1: Alert when a market goes above 0.65
    alert1_id = add_alert(
        market_id="example_market_1",
        direction="above",
        target_price=0.65,
    )
    print(f"  ✓ Added alert {alert1_id}: above 0.65")

    # Example 2: Alert when a market goes below 0.35
    alert2_id = add_alert(
        market_id="example_market_2",
        direction="below",
        target_price=0.35,
    )
    print(f"  ✓ Added alert {alert2_id}: below 0.35")

    # List all alerts
    print("\nCurrent alerts:")
    alerts = list_alerts()
    for alert in alerts:
        print(f"  - {alert['market_id']}: {alert['direction']} {alert['target_price']}")

    # Create the watcher
    print("\nCreating price alert watcher...")
    watcher = PriceAlertWatcher(
        api_client=api_client,
        alert_cooldown=300.0,  # 5 minutes between duplicate alerts
        on_alert_triggered=alert_callback,
    )

    print("✅ Watcher created\n")

    # Note: In a real scenario, you would start the watcher and let it run:
    # watcher.start()
    #
    # The watcher would then:
    # 1. Subscribe to WebSocket for all markets in the alert list
    # 2. Monitor price updates in real-time
    # 3. Check each update against alert thresholds
    # 4. Fire alerts when conditions are met (respecting cooldown)
    # 5. Call the alert_callback function for each triggered alert

    print("📝 Demonstration of manual alert checking:")
    print("-" * 70)

    # Simulate price updates manually for demonstration
    print("\nSimulating price update for example_market_1...")

    # Create a mock orderbook
    orderbook1 = NormalizedOrderBook(
        yes_best_bid=0.68,
        yes_best_ask=0.70,
        no_best_bid=0.30,
        no_best_ask=0.32,
        market_id="example_market_1",
    )

    print(f"  Current price: {orderbook1.yes_best_ask:.4f}")

    # Manually trigger the handler (in real usage, WebSocket would do this)
    watcher._running = True
    watcher._handle_price_update("example_market_1", orderbook1)

    print("\nSimulating price update for example_market_2...")

    orderbook2 = NormalizedOrderBook(
        yes_best_bid=0.28,
        yes_best_ask=0.30,
        no_best_bid=0.70,
        no_best_ask=0.72,
        market_id="example_market_2",
    )

    print(f"  Current price: {orderbook2.yes_best_ask:.4f}")

    watcher._handle_price_update("example_market_2", orderbook2)

    # Clean up
    print("\n" + "=" * 70)
    print("Cleaning up...")

    remove_alert(alert1_id)
    remove_alert(alert2_id)

    print("✅ Alerts removed")
    print("\n" + "=" * 70)
    print("Example complete!")
    print("=" * 70)

    print("\n💡 To use the watcher in production:")
    print("   1. Add alerts for real market IDs")
    print("   2. Call watcher.start() to begin monitoring")
    print("   3. The watcher will run in background thread")
    print("   4. It will fire alerts when thresholds are crossed")
    print("   5. Call watcher.stop() when done")
    print()


if __name__ == "__main__":
    main()
