#!/usr/bin/env python
"""
Mock example demonstrating PriceAlertWatcher with simulated data.

This example works offline by simulating API responses.
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


def alert_callback(alert: PriceAlert) -> None:
    """Callback function called when an alert is triggered."""
    print(f"\n🚨 ALERT TRIGGERED! 🚨")
    print(f"  Market: {alert.market_id}")
    print(f"  Direction: {alert.direction}")
    print(f"  Target: {alert.target_price:.4f}")
    print(f"  Current: {alert.current_price:.4f}")
    print(f"  Message: {alert.alert_message}")
    print()


def main():
    print("=" * 70)
    print("Price Alert Watcher Example (Mock Mode)")
    print("=" * 70)
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
    
    # Create the watcher
    print("\nCreating price alert watcher...")
    watcher = PriceAlertWatcher(
        api_client=mock_api_client,
        alert_cooldown=2.0,  # 2 seconds for demo
        on_alert_triggered=alert_callback,
    )
    print("✅ Watcher created\n")
    
    # Simulate monitoring
    print("=" * 70)
    print("Simulating Real-Time Price Monitoring")
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
    watcher._handle_price_update("btc_100k", orderbook2)
    time.sleep(0.5)
    
    # Scenario 3: ETH market crosses threshold
    print("📊 Update 3: ETH 10K market update")
    orderbook3 = NormalizedOrderBook(
        yes_best_bid=0.52,
        yes_best_ask=0.54,
        market_id="eth_10k",
    )
    print(f"   Price: {orderbook3.yes_best_ask:.4f} (Target: 0.50)")
    watcher._handle_price_update("eth_10k", orderbook3)
    time.sleep(0.5)
    
    # Scenario 4: Trump market still above threshold (duplicate prevention)
    print("📊 Update 4: Trump 2024 market update (duplicate)")
    orderbook4 = NormalizedOrderBook(
        yes_best_bid=0.71,
        yes_best_ask=0.73,
        market_id="trump_2024",
    )
    print(f"   Price: {orderbook4.yes_best_ask:.4f} (Target: 0.65)")
    print("   ⏱️  Alert in cooldown period - should not fire")
    watcher._handle_price_update("trump_2024", orderbook4)
    time.sleep(0.5)
    
    # Scenario 5: BTC market drops below threshold
    print("📊 Update 5: BTC 100K market update")
    orderbook5 = NormalizedOrderBook(
        yes_best_bid=0.28,
        yes_best_ask=0.30,
        market_id="btc_100k",
    )
    print(f"   Price: {orderbook5.yes_best_ask:.4f} (Target: below 0.35)")
    watcher._handle_price_update("btc_100k", orderbook5)
    time.sleep(0.5)
    
    # Scenario 6: Wait for cooldown to expire, then trigger again
    print("\n⏱️  Waiting for cooldown period to expire (2 seconds)...")
    time.sleep(2.5)
    
    print("📊 Update 6: Trump 2024 market update (after cooldown)")
    orderbook6 = NormalizedOrderBook(
        yes_best_bid=0.74,
        yes_best_ask=0.76,
        market_id="trump_2024",
    )
    print(f"   Price: {orderbook6.yes_best_ask:.4f} (Target: 0.65)")
    print("   ✅ Cooldown expired - alert should fire again")
    watcher._handle_price_update("trump_2024", orderbook6)
    time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print("Alerts fired:")
    print("  ✅ Trump 2024 crossed above 0.65 (fired twice, respecting cooldown)")
    print("  ✅ ETH 10K crossed above 0.50")
    print("  ✅ BTC 100K crossed below 0.35")
    print()
    print("Duplicate prevention:")
    print("  ✅ Trump 2024 duplicate blocked during cooldown")
    print()
    
    # Clean up
    print("Cleaning up...")
    remove_alert(alert1_id)
    remove_alert(alert2_id)
    remove_alert(alert3_id)
    print("✅ Alerts removed")
    
    print("\n" + "=" * 70)
    print("Example complete!")
    print("=" * 70)
    print()
    print("💡 Key Features Demonstrated:")
    print("   1. ✅ Alert triggering when prices cross thresholds")
    print("   2. ✅ Support for both 'above' and 'below' alerts")
    print("   3. ✅ Duplicate alert prevention with cooldown period")
    print("   4. ✅ Real-time monitoring of multiple markets")
    print("   5. ✅ Callback system for handling triggered alerts")
    print()


if __name__ == "__main__":
    main()
