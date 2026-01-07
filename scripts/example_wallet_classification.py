"""
Example script demonstrating wallet classification functionality.

This script shows how to use the wallet_classifier module to classify
wallets as fresh, whale, high-confidence, or suspicious cluster.
"""

from datetime import datetime

from app.core.wallet_feed import WalletFeed, WalletTrade
from app.core.wallet_classifier import (
    classify_wallet,
    detect_suspicious_cluster,
    store_wallet_tags,
    get_wallet_tags,
)
from app.core.config import get_config
from app.core.logger import logger


def main():
    """Run example wallet classification."""
    logger.info("=== Wallet Classification Example ===")

    # Get configuration
    config = get_config()

    # Initialize wallet feed
    feed = WalletFeed()

    # Example: Add some sample trades for demonstration
    logger.info("\n1. Adding sample wallet trades...")

    sample_trades = [
        # Fresh wallet with large trade (should be both fresh and whale)
        WalletTrade(
            wallet="0xfreshwhale123",
            market_id="market_election_2024",
            side="yes",
            price=0.65,
            size=25000.0,  # Large trade
            timestamp=datetime.now(),
            tx_hash="0xhash_freshwhale",
        ),
        # Regular fresh wallet
        WalletTrade(
            wallet="0xfresh456",
            market_id="market_election_2024",
            side="no",
            price=0.40,
            size=500.0,
            timestamp=datetime.now(),
            tx_hash="0xhash_fresh",
        ),
        # Another fresh wallet in same market (for cluster detection)
        WalletTrade(
            wallet="0xfresh789",
            market_id="market_election_2024",
            side="yes",
            price=0.62,
            size=300.0,
            timestamp=datetime.now(),
            tx_hash="0xhash_fresh2",
        ),
    ]

    feed.store_trades(sample_trades)
    logger.info(f"Stored {len(sample_trades)} sample trades")

    # Example: Classify individual wallets
    logger.info("\n2. Classifying individual wallets...")

    for wallet in ["0xfreshwhale123", "0xfresh456"]:
        logger.info(f"\nClassifying wallet: {wallet}")

        # Classify with configuration thresholds
        tags = classify_wallet(
            wallet,
            whale_threshold=config.whale_threshold_usd,
            high_confidence_roi_threshold=config.high_confidence_min_roi,
            high_confidence_win_rate_threshold=config.high_confidence_min_win_rate,
            high_confidence_min_trades=config.high_confidence_min_trades,
        )

        if tags:
            logger.info(f"  Found {len(tags)} classification(s):")
            for tag in tags:
                logger.info(f"    - {tag.tag} (confidence: {tag.confidence:.2f})")
                if tag.metadata:
                    logger.info(f"      Metadata: {tag.metadata}")

            # Store tags in database
            count = store_wallet_tags(tags)
            logger.info(f"  Stored {count} tags in database")
        else:
            logger.info("  No special classifications found")

    # Example: Detect suspicious clusters
    logger.info("\n3. Detecting suspicious clusters...")

    cluster_tags = detect_suspicious_cluster(
        "market_election_2024",
        min_fresh_wallets=config.suspicious_cluster_min_wallets,
        time_window_hours=config.suspicious_cluster_time_window_hours,
    )

    if cluster_tags:
        logger.info(
            f"  ⚠️  Suspicious cluster detected: {len(cluster_tags)} fresh wallets"
        )
        logger.info("  Wallets in cluster:")
        for tag in cluster_tags:
            logger.info(f"    - {tag.wallet}")

        # Store cluster tags
        count = store_wallet_tags(cluster_tags)
        logger.info(f"  Stored {count} cluster tags in database")
    else:
        logger.info(
            f"  No suspicious clusters detected "
            f"(threshold: {config.suspicious_cluster_min_wallets} wallets)"
        )

    # Example: Query stored tags
    logger.info("\n4. Querying stored wallet tags...")

    # Get all fresh wallet tags
    fresh_tags = get_wallet_tags(tag="fresh", limit=10)
    logger.info(f"\nFound {len(fresh_tags)} fresh wallet tag(s):")
    for tag_data in fresh_tags:
        logger.info(f"  - {tag_data['wallet']} (confidence: {tag_data['confidence']})")

    # Get all whale tags
    whale_tags = get_wallet_tags(tag="whale", limit=10)
    logger.info(f"\nFound {len(whale_tags)} whale tag(s):")
    for tag_data in whale_tags:
        logger.info(f"  - {tag_data['wallet']} (confidence: {tag_data['confidence']})")

    # Get all suspicious cluster tags
    cluster_tags_db = get_wallet_tags(tag="suspicious_cluster", limit=10)
    logger.info(f"\nFound {len(cluster_tags_db)} suspicious cluster tag(s):")
    for tag_data in cluster_tags_db:
        logger.info(f"  - {tag_data['wallet']} (confidence: {tag_data['confidence']})")

    # Get tags for specific wallet
    specific_wallet = "0xfreshwhale123"
    wallet_tags = get_wallet_tags(wallet=specific_wallet)
    logger.info(f"\nTags for wallet {specific_wallet}:")
    for tag_data in wallet_tags:
        logger.info(f"  - {tag_data['tag']} (confidence: {tag_data['confidence']})")

    logger.info("\n=== Example Complete ===")
    logger.info("\nNext steps:")
    logger.info("  - Configure thresholds in .env file")
    logger.info("  - Integrate classification into your wallet monitoring workflow")
    logger.info("  - Query wallet_tags table for analysis and alerts")


if __name__ == "__main__":
    main()
