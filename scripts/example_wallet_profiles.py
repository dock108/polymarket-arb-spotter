#!/usr/bin/env python
"""
Example script demonstrating wallet profile analytics.

This script shows how to:
1. Get profile for a specific wallet
2. Rank wallets by different metrics
3. Analyze wallet trading patterns
"""

import os
import tempfile
from datetime import datetime

from app.core.wallet_feed import WalletFeed, WalletTrade
from app.core.wallet_profiles import (
    get_wallet_profile,
    rank_wallets,
    get_all_wallet_profiles,
)


def main():
    """Demonstrate wallet profile functionality."""

    # Use a temporary database for demonstration to avoid conflicts
    temp_dir = tempfile.gettempdir()
    db_path = os.path.join(temp_dir, "example_wallet_profiles.db")

    print("=" * 70)
    print("Wallet Profile Analytics Demo")
    print("=" * 70)
    print(f"Using database: {db_path}")
    print()

    # Initialize wallet feed
    feed = WalletFeed(db_path=db_path)

    # Create sample trades for demonstration
    print("\n1. Creating sample trade data...")
    sample_trades = [
        # Wallet 1: Good trader
        WalletTrade(
            wallet="0xSmartWallet1",
            market_id="market_election",
            side="yes",
            price=0.45,
            size=1000.0,
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            tx_hash="0xhash1",
        ),
        WalletTrade(
            wallet="0xSmartWallet1",
            market_id="market_sports",
            side="no",
            price=0.35,
            size=500.0,
            timestamp=datetime(2024, 1, 2, 11, 0, 0),
            tx_hash="0xhash2",
        ),
        WalletTrade(
            wallet="0xSmartWallet1",
            market_id="market_crypto",
            side="yes",
            price=0.60,
            size=750.0,
            timestamp=datetime(2024, 1, 3, 12, 0, 0),
            tx_hash="0xhash3",
        ),
        # Wallet 2: Average trader
        WalletTrade(
            wallet="0xAverageWallet2",
            market_id="market_election",
            side="no",
            price=0.55,
            size=300.0,
            timestamp=datetime(2024, 1, 1, 14, 0, 0),
            tx_hash="0xhash4",
        ),
        WalletTrade(
            wallet="0xAverageWallet2",
            market_id="market_sports",
            side="yes",
            price=0.65,
            size=200.0,
            timestamp=datetime(2024, 1, 2, 15, 0, 0),
            tx_hash="0xhash5",
        ),
        # Wallet 3: High volume trader
        WalletTrade(
            wallet="0xWhaleWallet3",
            market_id="market_election",
            side="yes",
            price=0.50,
            size=5000.0,
            timestamp=datetime(2024, 1, 1, 16, 0, 0),
            tx_hash="0xhash6",
        ),
        WalletTrade(
            wallet="0xWhaleWallet3",
            market_id="market_crypto",
            side="no",
            price=0.40,
            size=3000.0,
            timestamp=datetime(2024, 1, 3, 17, 0, 0),
            tx_hash="0xhash7",
        ),
    ]

    stored_count = feed.store_trades(sample_trades)
    print(f"   Stored {stored_count} trades")

    # Define market outcomes for ROI/win rate calculation
    market_outcomes = {
        "market_election": {"outcome": "yes", "resolved": True},
        "market_sports": {"outcome": "no", "resolved": True},
        "market_crypto": {"outcome": "yes", "resolved": True},
    }

    # 2. Get profile for a specific wallet
    print("\n2. Getting profile for specific wallet...")
    print("-" * 70)

    wallet_address = "0xSmartWallet1"
    profile = get_wallet_profile(
        wallet_address,
        market_outcomes=market_outcomes,
        db_path=db_path,
    )

    if profile:
        print(f"\nWallet: {profile.wallet}")
        print(f"Total Trades: {profile.total_trades}")
        print(f"Average Entry Price: {profile.avg_entry_price:.3f}")
        print(f"Total Volume: ${profile.total_volume:.2f}")
        print(f"Markets Traded: {len(profile.markets_traded)}")
        print(f"  - {', '.join(profile.markets_traded)}")
        print("\nPerformance Metrics (from resolved markets):")
        print(f"  Resolved Markets: {profile.realized_outcomes}")
        print(f"  Win Rate: {profile.win_rate:.1f}%")
        print(f"  Total Profit: ${profile.total_profit:.2f}")
        print(f"  Average ROI: {profile.avg_roi:.1f}%")

    # 3. Rank wallets by different metrics
    print("\n\n3. Ranking wallets by different metrics...")
    print("-" * 70)

    # Rank by volume
    print("\n📊 Top Wallets by Trading Volume:")
    top_by_volume = rank_wallets(
        by="volume",
        market_outcomes=market_outcomes,
        min_trades=1,
        limit=10,
        db_path=db_path,
    )

    for i, profile in enumerate(top_by_volume, 1):
        print(f"  {i}. {profile.wallet[:20]}... - Volume: ${profile.total_volume:.2f}")

    # Rank by win rate
    print("\n🏆 Top Wallets by Win Rate:")
    top_by_win_rate = rank_wallets(
        by="win_rate",
        market_outcomes=market_outcomes,
        min_trades=1,
        limit=10,
        db_path=db_path,
    )

    for i, profile in enumerate(top_by_win_rate, 1):
        print(
            f"  {i}. {profile.wallet[:20]}... - "
            f"Win Rate: {profile.win_rate:.1f}% "
            f"({profile.total_trades} trades)"
        )

    # Rank by profit
    print("\n💰 Top Wallets by Total Profit:")
    top_by_profit = rank_wallets(
        by="profit",
        market_outcomes=market_outcomes,
        min_trades=1,
        limit=10,
        db_path=db_path,
    )

    for i, profile in enumerate(top_by_profit, 1):
        print(
            f"  {i}. {profile.wallet[:20]}... - "
            f"Profit: ${profile.total_profit:.2f} "
            f"(ROI: {profile.avg_roi:.1f}%)"
        )

    # Rank by ROI
    print("\n📈 Top Wallets by ROI:")
    top_by_roi = rank_wallets(
        by="roi",
        market_outcomes=market_outcomes,
        min_trades=1,
        limit=10,
        db_path=db_path,
    )

    for i, profile in enumerate(top_by_roi, 1):
        print(
            f"  {i}. {profile.wallet[:20]}... - "
            f"ROI: {profile.avg_roi:.1f}% "
            f"(Profit: ${profile.total_profit:.2f})"
        )

    # 4. Get all profiles
    print("\n\n4. Getting all wallet profiles...")
    print("-" * 70)

    all_profiles = get_all_wallet_profiles(
        market_outcomes=market_outcomes,
        min_trades=1,
        db_path=db_path,
    )

    print(f"\nTotal wallets tracked: {len(all_profiles)}")
    print("\nSummary Statistics:")

    if all_profiles:
        total_volume = sum(p.total_volume for p in all_profiles)
        avg_win_rate = sum(p.win_rate for p in all_profiles) / len(all_profiles)
        total_trades = sum(p.total_trades for p in all_profiles)

        print(f"  Total Trading Volume: ${total_volume:.2f}")
        print(f"  Average Win Rate: {avg_win_rate:.1f}%")
        print(f"  Total Trades Tracked: {total_trades}")

    print("\n" + "=" * 70)
    print("Finding 'Smart Wallets':")
    print("=" * 70)
    print("\nCriteria for smart wallets:")
    print("  - At least 2 trades (to show consistency)")
    print("  - Win rate > 60%")
    print("  - Positive ROI")

    smart_wallets = [
        p
        for p in all_profiles
        if p.total_trades >= 2 and p.win_rate > 60 and p.avg_roi > 0
    ]

    if smart_wallets:
        print(f"\n✨ Found {len(smart_wallets)} smart wallet(s):\n")
        for profile in smart_wallets:
            print(f"  Wallet: {profile.wallet}")
            print(f"    - Trades: {profile.total_trades}")
            print(f"    - Win Rate: {profile.win_rate:.1f}%")
            print(f"    - ROI: {profile.avg_roi:.1f}%")
            print(f"    - Profit: ${profile.total_profit:.2f}")
            print(f"    - Markets: {', '.join(profile.markets_traded)}")
            print()
    else:
        print("\n  No wallets meet the smart wallet criteria yet.")

    print("\n" + "=" * 70)
    print("Demo completed successfully!")
    print("=" * 70)

    # Clean up temporary database
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"\nCleaned up temporary database: {db_path}")


if __name__ == "__main__":
    main()
