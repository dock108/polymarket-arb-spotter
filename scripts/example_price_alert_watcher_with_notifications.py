#!/usr/bin/env python
"""
Mock example demonstrating PriceAlertWatcher with send_price_alert integration.

This example shows how to integrate send_price_alert with PriceAlertWatcher
to send notifications when price thresholds are crossed. Demonstrates that
errors in notification sending don't crash the monitoring loop.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.api_client import NormalizedOrderBook
from app.core.price_alerts import (
    PriceAlertWatcher,
    PriceAlert,
    add_alert,
    list_alerts,
    remove_alert,
)
from app.core.notifications import send_price_alert
from app.core.config import get_config


def alert_callback_with_notification(alert: PriceAlert) -> None:
    """
    Callback function that sends notifications when alerts are triggered.
    
    This demonstrates how to integrate send_price_alert with the watcher.
    The send_price_alert function handles errors gracefully, so failures
    won't crash the monitoring loop.
    """
    print(f"\n🚨 ALERT TRIGGERED! 🚨")
    print(f"  Market: {alert.market_id}")
    print(f"  Direction: {alert.direction}")
    print(f"  Target: {alert.target_price:.4f}")
    print(f"  Current: {alert.current_price:.4f}")
    print(f"  Message: {alert.alert_message}")
    
    # Send notification - errors won't crash the loop
    print(f"  📧 Sending notification...")
    success = send_price_alert(alert)
    
    if success:
        print(f"  ✓ Notification sent successfully!")
    else:
        print(f"  ℹ️  Notification logged (or failed gracefully)")
    
    print()


def main():
    print("=" * 70)
    print("Price Alert Watcher + Notification Integration Example")
    print("=" * 70)
    print()
    
    # Show notification config
    config = get_config()
    print("Notification Configuration:")
    print(f"  Method: {config.alert_method or 'Disabled (will log instead)'}")
    print()
    
    # Create a mock API client
    print("Creating mock API client...")
    mock_api_client = MagicMock()
    mock_api_client.stop_websocket = MagicMock()
    print("✅ Mock API client created\n")
    
    # Add example alerts
    print("Adding example alerts...")
    
    alert1_id = add_alert(
        market_id="trump_2024",
        direction="above",
        target_price=0.65,
    )
    print(f"  ✓ Added alert: Trump 2024 above 0.65")
    
    alert2_id = add_alert(
        market_id="btc_100k",
        direction="below",
        target_price=0.35,
    )
    print(f"  ✓ Added alert: BTC 100K below 0.35")
    
    alert3_id = add_alert(
        market_id="eth_10k",
        direction="above",
        target_price=0.50,
    )
    print(f"  ✓ Added alert: ETH 10K above 0.50")
    
    # List all alerts
    print("\nCurrent alerts:")
    alerts = list_alerts()
    for alert in alerts:
        print(f"  - {alert['market_id']}: {alert['direction']} {alert['target_price']:.4f}")
    
    # Create the watcher with notification callback
    print("\nCreating price alert watcher with notification integration...")
    watcher = PriceAlertWatcher(
        api_client=mock_api_client,
        alert_cooldown=2.0,  # 2 seconds for demo
        on_alert_triggered=alert_callback_with_notification,  # Integration point!
    )
    print("✅ Watcher created\n")
    
    # Simulate monitoring
    print("=" * 70)
    print("Simulating Real-Time Price Monitoring with Notifications")
    print("=" * 70)
    print()
    
    watcher._running = True
    
    # Scenario 1: Trump market moves above threshold
    print("📊 Update 1: Trump 2024 market update")
    orderbook1 = NormalizedOrderBook(
        yes_best_bid=0.68,
        yes_best_ask=0.70,
        market_id="trump_2024",
    )
    print(f"   Price: {orderbook1.yes_best_ask:.4f} (Target: 0.65)")
    watcher._handle_price_update("trump_2024", orderbook1)
    time.sleep(0.5)
    
    # Scenario 2: BTC market stays above threshold (no alert)
    print("📊 Update 2: BTC 100K market update")
    orderbook2 = NormalizedOrderBook(
        yes_best_bid=0.58,
        yes_best_ask=0.60,
        market_id="btc_100k",
    )
    print(f"   Price: {orderbook2.yes_best_ask:.4f} (Target: below 0.35)")
    print("   No alert triggered (price not below threshold)")
    watcher._handle_price_update("btc_100k", orderbook2)
    time.sleep(0.5)
    
    # Scenario 3: ETH market crosses threshold
    print("\n📊 Update 3: ETH 10K market update")
    orderbook3 = NormalizedOrderBook(
        yes_best_bid=0.52,
        yes_best_ask=0.54,
        market_id="eth_10k",
    )
    print(f"   Price: {orderbook3.yes_best_ask:.4f} (Target: 0.50)")
    watcher._handle_price_update("eth_10k", orderbook3)
    time.sleep(0.5)
    
    # Scenario 4: BTC market drops below threshold
    print("\n📊 Update 4: BTC 100K market update")
    orderbook5 = NormalizedOrderBook(
        yes_best_bid=0.28,
        yes_best_ask=0.30,
        market_id="btc_100k",
    )
    print(f"   Price: {orderbook5.yes_best_ask:.4f} (Target: below 0.35)")
    watcher._handle_price_update("btc_100k", orderbook5)
    time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print("✅ Demonstrated features:")
    print("  1. Integration of send_price_alert with PriceAlertWatcher")
    print("  2. Graceful error handling - failures don't crash the loop")
    print("  3. Notifications sent (or logged) when thresholds are crossed")
    print("  4. Real-time monitoring of multiple markets")
    print()
    
    if not config.alert_method:
        print("💡 Note: Notifications are disabled, so alerts were logged instead")
        print("   To enable notifications:")
        print("   - Copy .env.example to .env")
        print("   - Set ALERT_METHOD to 'telegram' or 'email'")
        print("   - Configure required credentials")
    else:
        print(f"✓ Notifications are enabled via {config.alert_method}")
    
    print()
    
    # Clean up
    print("Cleaning up...")
    remove_alert(alert1_id)
    remove_alert(alert2_id)
    remove_alert(alert3_id)
    print("✅ Alerts removed")
    
    print("\n" + "=" * 70)
    print("Integration Pattern")
    print("=" * 70)
    print("""
The key integration pattern demonstrated here:

from app.core.notifications import send_price_alert
from app.core.price_alerts import PriceAlertWatcher

# Define callback that sends notifications
def handle_alert(alert):
    # send_price_alert handles errors gracefully
    # so failures won't crash the monitoring loop
    send_price_alert(alert)

# Create watcher with the callback
watcher = PriceAlertWatcher(
    api_client=api_client,
    alert_cooldown=300.0,  # 5 minutes
    on_alert_triggered=handle_alert  # <-- Integration point
)

# Start monitoring
watcher.start()

# The watcher will:
# 1. Monitor markets via WebSocket
# 2. Check prices against thresholds
# 3. Trigger alerts when conditions are met
# 4. Call handle_alert() which sends notifications
# 5. Continue running even if notification fails
""")
    print("=" * 70)


if __name__ == "__main__":
    main()
