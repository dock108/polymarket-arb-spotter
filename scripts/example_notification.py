#!/usr/bin/env python
"""
Example script demonstrating the notification service.

This script shows how to use the notification service to send
alerts when arbitrage opportunities are detected.

Usage:
    python scripts/example_notification.py
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.notifications import send_alert, get_notification_service
from app.core.config import get_config


def main():
    """Demonstrate notification service usage."""
    
    print("Polymarket Arbitrage Spotter - Notification Example")
    print("=" * 60)
    
    # Get config to show current settings
    config = get_config()
    
    print(f"\nCurrent Configuration:")
    print(f"  Alert Method: {config.alert_method or 'None (disabled)'}")
    if config.alert_method == "telegram":
        print(f"  Telegram API Key: {'✓ Configured' if config.telegram_api_key else '✗ Missing'}")
        print(f"  Telegram Chat ID: {'✓ Configured' if config.telegram_chat_id else '✗ Missing'}")
    elif config.alert_method == "email":
        print(f"  Email SMTP Server: {config.email_smtp_server or '✗ Missing'}")
        print(f"  Email Configured: {'✓ Yes' if all([config.email_username, config.email_password, config.email_from, config.email_to]) else '✗ No'}")
    print(f"  Throttle: {config.notification_throttle_seconds} seconds")
    
    # Create a sample alert
    sample_alert = {
        'market_id': 'example_market_123',
        'market_name': 'Will Bitcoin hit $100k by end of 2024?',
        'expected_profit_pct': 2.5,
        'prices': {
            'yes_price': 0.48,
            'no_price': 0.50
        },
        'sum_price': 0.98,
        'timestamp': datetime.now().isoformat(),
        'threshold': 0.985,
        'profit_margin': 0.02
    }
    
    print("\n" + "=" * 60)
    print("Sample Alert Object:")
    print("-" * 60)
    for key, value in sample_alert.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("Attempting to send notification...")
    print("-" * 60)
    
    # Try to send the alert
    success = send_alert(sample_alert)
    
    if success:
        print("✓ Notification sent successfully!")
    else:
        if not config.alert_method:
            print("✗ No alert method configured.")
            print("\nTo enable notifications:")
            print("  1. Copy .env.example to .env")
            print("  2. Set ALERT_METHOD to 'telegram' or 'email'")
            print("  3. Configure the required credentials")
        else:
            print(f"✗ Failed to send notification via {config.alert_method}.")
            print("  Check the logs for details.")
    
    print("\n" + "=" * 60)
    print("Example complete!")
    print("\nFor production use:")
    print("  1. Configure environment variables in .env")
    print("  2. Import and call send_alert() when opportunities are detected")
    print("  3. The service will handle throttling automatically")
    print("\nExample code:")
    print("  from app.core.notifications import send_alert")
    print("  ")
    print("  # When you detect an arbitrage opportunity:")
    print("  alert = {")
    print("      'market_name': market['name'],")
    print("      'expected_profit_pct': profit_pct,")
    print("      'prices': {'yes_price': yes_price, 'no_price': no_price},")
    print("      'sum_price': sum_price,")
    print("      'timestamp': datetime.now().isoformat()")
    print("  }")
    print("  send_alert(alert)")
    print("=" * 60)


if __name__ == "__main__":
    main()
