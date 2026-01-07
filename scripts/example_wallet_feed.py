#!/usr/bin/env python
"""
Example script demonstrating wallet event ingestion.

This script shows how to use the WalletFeed class to:
1. Fetch trades from Polymarket
2. Store them in the database
3. Subscribe to real-time trades (via polling)
"""

import time
from datetime import datetime

from app.core.wallet_feed import WalletFeed, get_wallet_trades
from app.core.logger import logger


def example_fetch_and_store():
    """Example: Fetch trades and store them in database."""
    print("\n=== Example: Fetch and Store Trades ===\n")
    
    # Initialize wallet feed
    feed = WalletFeed()
    
    # Fetch trades for a specific market (if available)
    # Note: Replace with actual market_id when testing
    market_id = None  # Set to None to fetch all trades
    
    print(f"Fetching trades (market_id={market_id})...")
    trades = feed.fetch_trades(market_id=market_id, limit=10)
    
    print(f"Fetched {len(trades)} trades")
    for trade in trades[:3]:  # Show first 3
        print(f"  - {trade.wallet[:10]}... | {trade.market_id} | "
              f"{trade.side} @ ${trade.price:.3f} | size: {trade.size}")
    
    # Store trades in database
    if trades:
        count = feed.store_trades(trades)
        print(f"\nStored {count} new trades (duplicates filtered)")
    else:
        print("\nNo trades to store")


def example_ingest_trades():
    """Example: Fetch and store in one operation."""
    print("\n=== Example: Ingest Trades ===\n")
    
    feed = WalletFeed()
    
    # Ingest trades (fetch + store)
    count = feed.ingest_trades(limit=20)
    print(f"Ingested {count} new trades")


def example_query_trades():
    """Example: Query stored trades from database."""
    print("\n=== Example: Query Stored Trades ===\n")
    
    # Get all trades
    all_trades = get_wallet_trades(limit=5)
    print(f"Total trades (last 5): {len(all_trades)}")
    
    for trade in all_trades:
        print(f"  - {trade['wallet'][:10]}... | {trade['market_id']} | "
              f"{trade['side']} @ ${trade['price']:.3f} | {trade['timestamp']}")
    
    # Filter by wallet (example - replace with actual wallet)
    if all_trades:
        wallet = all_trades[0]['wallet']
        wallet_trades = get_wallet_trades(wallet=wallet, limit=10)
        print(f"\nTrades for wallet {wallet[:10]}...: {len(wallet_trades)}")


def example_subscribe_to_trades():
    """Example: Subscribe to real-time trade events."""
    print("\n=== Example: Subscribe to Trades (Polling) ===\n")
    print("Note: This will run for 30 seconds, polling every 10 seconds")
    print("Press Ctrl+C to stop early\n")
    
    feed = WalletFeed()
    
    trade_count = 0
    start_time = time.time()
    max_duration = 30  # seconds
    
    def on_trade(trade):
        """Callback function called for each new trade."""
        nonlocal trade_count
        trade_count += 1
        
        print(f"New trade #{trade_count}:")
        print(f"  Wallet: {trade.wallet[:10]}...")
        print(f"  Market: {trade.market_id}")
        print(f"  Side: {trade.side}")
        print(f"  Price: ${trade.price:.3f}")
        print(f"  Size: {trade.size}")
        print(f"  Time: {trade.timestamp}")
        print()
    
    try:
        # Start subscription in a separate thread to allow timeout
        import threading
        
        def subscribe():
            feed.subscribe_to_trades(
                on_trade=on_trade,
                poll_interval=10.0,  # Poll every 10 seconds
                auto_store=True,  # Automatically store in database
            )
        
        subscription_thread = threading.Thread(target=subscribe, daemon=True)
        subscription_thread.start()
        
        # Wait for max_duration
        while time.time() - start_time < max_duration:
            time.sleep(1)
        
        print(f"\nSubscription completed. Total new trades: {trade_count}")
        
    except KeyboardInterrupt:
        print(f"\nSubscription interrupted. Total new trades: {trade_count}")


def main():
    """Run all examples."""
    print("="*60)
    print("Wallet Feed Examples")
    print("="*60)
    
    try:
        # Example 1: Fetch and store
        example_fetch_and_store()
        
        # Example 2: Ingest (fetch + store in one call)
        example_ingest_trades()
        
        # Example 3: Query stored trades
        example_query_trades()
        
        # Example 4: Subscribe to real-time trades (optional - commented out by default)
        # Uncomment to test real-time subscription
        # example_subscribe_to_trades()
        
    except Exception as e:
        logger.error(f"Error in example: {e}", exc_info=True)
        print(f"\nError: {e}")
    
    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)


if __name__ == "__main__":
    main()
