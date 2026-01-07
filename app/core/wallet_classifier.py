"""
Wallet classification for Polymarket traders.

This module provides functionality to classify wallets based on their trading patterns
and behavior, including fresh wallets, whales, high-confidence wallets, and suspicious
clusters.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlite_utils import Database

from app.core.logger import logger
from app.core.wallet_feed import _WALLET_TRADES_DB_PATH, _ensure_table, _get_db


# Default database path for wallet tags (uses same DB as wallet trades)
_WALLET_TAGS_DB_PATH = _WALLET_TRADES_DB_PATH


@dataclass
class WalletTag:
    """Tag/classification for a wallet."""

    wallet: str
    tag: str  # "fresh", "whale", "high_confidence", "suspicious_cluster"
    confidence: float  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "wallet": self.wallet,
            "tag": self.tag,
            "confidence": self.confidence,
            "metadata": str(self.metadata),  # Store as JSON string
            "timestamp": self.timestamp.isoformat(),
        }


def _ensure_wallet_tags_table(db: Database) -> None:
    """
    Ensure the wallet_tags table exists with proper schema and indexes.

    Args:
        db: Database instance
    """
    if "wallet_tags" not in db.table_names():
        db["wallet_tags"].create(
            {
                "wallet": str,
                "tag": str,
                "confidence": float,
                "metadata": str,  # JSON string
                "timestamp": str,
            },
            pk="id",
        )
        logger.debug("Created wallet_tags table")

    # Create indexes for efficient queries
    db["wallet_tags"].create_index(
        ["wallet"],
        index_name="idx_wallet_tags_wallet",
        if_not_exists=True,
    )
    db["wallet_tags"].create_index(
        ["tag"],
        index_name="idx_wallet_tags_tag",
        if_not_exists=True,
    )
    db["wallet_tags"].create_index(
        ["wallet", "tag"],
        index_name="idx_wallet_tags_wallet_tag",
        if_not_exists=True,
    )


def classify_fresh_wallet(
    wallet: str,
    reference_date: Optional[datetime] = None,
    db_path: str = _WALLET_TRADES_DB_PATH,
) -> Optional[WalletTag]:
    """
    Classify wallet as "fresh" if it has no trade history before the reference date.

    Args:
        wallet: Wallet address
        reference_date: Reference date to check against (defaults to start of today)
        db_path: Path to wallet trades database

    Returns:
        WalletTag if wallet is fresh, None otherwise
    """
    try:
        db = _get_db(db_path)
        _ensure_table(db)

        # Default to start of today (00:00:00)
        if reference_date is None:
            reference_date = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        reference_str = reference_date.isoformat()

        # Check for trades before reference date
        query = """
            SELECT COUNT(*) FROM wallet_trades
            WHERE wallet = ? AND timestamp < ?
        """
        count = db.execute(query, [wallet, reference_str]).fetchone()[0]

        if count == 0:
            # Check if wallet has any trades at all
            total_query = "SELECT COUNT(*) FROM wallet_trades WHERE wallet = ?"
            total_count = db.execute(total_query, [wallet]).fetchone()[0]

            if total_count > 0:
                # Wallet has trades, but all are after reference date
                logger.debug(f"Wallet {wallet} classified as fresh")
                return WalletTag(
                    wallet=wallet,
                    tag="fresh",
                    confidence=1.0,
                    metadata={
                        "reference_date": reference_str,
                        "total_trades": total_count,
                    },
                )

        return None

    except Exception as e:
        logger.error(f"Error classifying fresh wallet: {e}", exc_info=True)
        return None


def classify_whale(
    wallet: str,
    trade_size_threshold: float = 10000.0,
    db_path: str = _WALLET_TRADES_DB_PATH,
) -> Optional[WalletTag]:
    """
    Classify wallet as "whale" if it has trades above the size threshold.

    Args:
        wallet: Wallet address
        trade_size_threshold: Minimum trade size (in USD) to classify as whale
        db_path: Path to wallet trades database

    Returns:
        WalletTag if wallet is a whale, None otherwise
    """
    try:
        db = _get_db(db_path)
        _ensure_table(db)

        # Check for large trades
        query = """
            SELECT COUNT(*) as large_trades, MAX(size) as max_trade, AVG(size) as avg_trade
            FROM wallet_trades
            WHERE wallet = ? AND size >= ?
        """
        result = db.execute(query, [wallet, trade_size_threshold]).fetchone()

        if result and result[0] > 0:
            large_trades, max_trade, avg_trade = result
            logger.debug(
                f"Wallet {wallet} classified as whale: {large_trades} large trades, max: {max_trade}"
            )
            return WalletTag(
                wallet=wallet,
                tag="whale",
                confidence=1.0,
                metadata={
                    "threshold": trade_size_threshold,
                    "large_trades_count": large_trades,
                    "max_trade_size": max_trade,
                    "avg_large_trade_size": avg_trade,
                },
            )

        return None

    except Exception as e:
        logger.error(f"Error classifying whale: {e}", exc_info=True)
        return None


def classify_high_confidence(
    wallet: str,
    min_roi_threshold: float = 10.0,
    min_win_rate_threshold: float = 60.0,
    min_trades: int = 5,
    db_path: str = _WALLET_TRADES_DB_PATH,
) -> Optional[WalletTag]:
    """
    Classify wallet as "high_confidence" if it is historically profitable.

    Requires both high ROI and win rate with minimum number of trades.

    Args:
        wallet: Wallet address
        min_roi_threshold: Minimum average ROI percentage (default: 10%)
        min_win_rate_threshold: Minimum win rate percentage (default: 60%)
        min_trades: Minimum number of trades required for classification
        db_path: Path to wallet trades database

    Returns:
        WalletTag if wallet is high confidence, None otherwise

    Note:
        This classification requires market outcome data to calculate profitability.
        Without outcome data, it cannot determine if a wallet is high-confidence.
    """
    try:
        # Import here to avoid circular dependency
        from app.core.wallet_profiles import get_wallet_profile

        # Get wallet profile with statistics
        profile = get_wallet_profile(wallet, market_outcomes=None, db_path=db_path)

        if profile is None:
            return None

        # Check minimum trades requirement
        if profile.total_trades < min_trades:
            return None

        # Check if we have outcome data (realized_outcomes > 0)
        if profile.realized_outcomes == 0:
            # Cannot determine profitability without market outcomes
            logger.debug(
                f"Cannot classify {wallet} as high-confidence: no resolved market data"
            )
            return None

        # Check ROI and win rate thresholds
        if (
            profile.avg_roi >= min_roi_threshold
            and profile.win_rate >= min_win_rate_threshold
        ):
            logger.debug(
                f"Wallet {wallet} classified as high-confidence: "
                f"ROI={profile.avg_roi:.2f}%, win_rate={profile.win_rate:.2f}%"
            )

            # Calculate confidence based on how far above thresholds
            roi_factor = min(profile.avg_roi / min_roi_threshold, 2.0)
            win_rate_factor = min(profile.win_rate / min_win_rate_threshold, 2.0)
            confidence = min((roi_factor + win_rate_factor) / 4.0, 1.0)

            return WalletTag(
                wallet=wallet,
                tag="high_confidence",
                confidence=confidence,
                metadata={
                    "avg_roi": profile.avg_roi,
                    "win_rate": profile.win_rate,
                    "total_trades": profile.total_trades,
                    "realized_outcomes": profile.realized_outcomes,
                    "total_profit": profile.total_profit,
                },
            )

        return None

    except Exception as e:
        logger.error(f"Error classifying high-confidence wallet: {e}", exc_info=True)
        return None


def detect_suspicious_cluster(
    market_id: str,
    min_fresh_wallets: int = 3,
    time_window_hours: float = 24.0,
    reference_date: Optional[datetime] = None,
    db_path: str = _WALLET_TRADES_DB_PATH,
) -> List[WalletTag]:
    """
    Detect suspicious cluster: multiple fresh wallets trading in the same market.

    Args:
        market_id: Market ID to check
        min_fresh_wallets: Minimum number of fresh wallets to flag as suspicious
        time_window_hours: Time window to consider for clustering (in hours)
        reference_date: Reference date for "fresh" classification (defaults to start of today)
        db_path: Path to wallet trades database

    Returns:
        List of WalletTag objects for wallets in suspicious cluster, empty if none detected
    """
    try:
        db = _get_db(db_path)
        _ensure_table(db)

        # Default to start of today
        if reference_date is None:
            reference_date = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        reference_str = reference_date.isoformat()

        # Calculate time window start
        window_start = datetime.now() - timedelta(hours=time_window_hours)
        window_start_str = window_start.isoformat()

        # Find wallets that:
        # 1. Traded in this market recently (within time window)
        # 2. Have no trades before reference date (fresh wallets)
        query = """
            SELECT DISTINCT wt.wallet
            FROM wallet_trades wt
            WHERE wt.market_id = ?
              AND wt.timestamp >= ?
              AND wt.wallet NOT IN (
                  SELECT DISTINCT wallet
                  FROM wallet_trades
                  WHERE timestamp < ?
              )
        """
        rows = db.execute(query, [market_id, window_start_str, reference_str]).fetchall()

        fresh_wallets = [row[0] for row in rows]

        if len(fresh_wallets) >= min_fresh_wallets:
            logger.warning(
                f"Suspicious cluster detected in market {market_id}: "
                f"{len(fresh_wallets)} fresh wallets"
            )

            # Create tags for all wallets in cluster
            tags = []
            for wallet in fresh_wallets:
                tag = WalletTag(
                    wallet=wallet,
                    tag="suspicious_cluster",
                    confidence=min(len(fresh_wallets) / min_fresh_wallets, 1.0),
                    metadata={
                        "market_id": market_id,
                        "cluster_size": len(fresh_wallets),
                        "time_window_hours": time_window_hours,
                        "reference_date": reference_str,
                    },
                )
                tags.append(tag)

            return tags

        return []

    except Exception as e:
        logger.error(f"Error detecting suspicious cluster: {e}", exc_info=True)
        return []


def classify_wallet(
    wallet: str,
    whale_threshold: float = 10000.0,
    high_confidence_roi_threshold: float = 10.0,
    high_confidence_win_rate_threshold: float = 60.0,
    high_confidence_min_trades: int = 5,
    reference_date: Optional[datetime] = None,
    db_path: str = _WALLET_TRADES_DB_PATH,
) -> List[WalletTag]:
    """
    Classify a wallet with all applicable tags.

    Args:
        wallet: Wallet address
        whale_threshold: USD threshold for whale classification
        high_confidence_roi_threshold: Minimum ROI % for high-confidence
        high_confidence_win_rate_threshold: Minimum win rate % for high-confidence
        high_confidence_min_trades: Minimum trades for high-confidence
        reference_date: Reference date for fresh wallet classification
        db_path: Path to wallet trades database

    Returns:
        List of applicable WalletTag objects
    """
    tags = []

    # Check fresh wallet
    fresh_tag = classify_fresh_wallet(wallet, reference_date, db_path)
    if fresh_tag:
        tags.append(fresh_tag)

    # Check whale
    whale_tag = classify_whale(wallet, whale_threshold, db_path)
    if whale_tag:
        tags.append(whale_tag)

    # Check high-confidence
    high_conf_tag = classify_high_confidence(
        wallet,
        high_confidence_roi_threshold,
        high_confidence_win_rate_threshold,
        high_confidence_min_trades,
        db_path,
    )
    if high_conf_tag:
        tags.append(high_conf_tag)

    return tags


def store_wallet_tag(
    tag: WalletTag,
    db_path: str = _WALLET_TAGS_DB_PATH,
) -> bool:
    """
    Store a wallet tag in the database.

    Args:
        tag: WalletTag object to store
        db_path: Path to wallet tags database

    Returns:
        True if tag was stored successfully, False otherwise
    """
    try:
        db = _get_db(db_path)
        _ensure_wallet_tags_table(db)

        # Store tag
        tag_data = tag.to_dict()
        db["wallet_tags"].insert(tag_data)

        logger.debug(f"Stored tag '{tag.tag}' for wallet {tag.wallet}")
        return True

    except Exception as e:
        logger.error(f"Error storing wallet tag: {e}", exc_info=True)
        return False


def store_wallet_tags(
    tags: List[WalletTag],
    db_path: str = _WALLET_TAGS_DB_PATH,
) -> int:
    """
    Store multiple wallet tags in the database.

    Args:
        tags: List of WalletTag objects to store
        db_path: Path to wallet tags database

    Returns:
        Number of tags successfully stored
    """
    if not tags:
        return 0

    try:
        db = _get_db(db_path)
        _ensure_wallet_tags_table(db)

        # Prepare tag data for batch insert
        tag_data = [tag.to_dict() for tag in tags]

        # Batch insert
        db["wallet_tags"].insert_all(tag_data)
        logger.debug(f"Batch stored {len(tag_data)} wallet tags")
        return len(tag_data)

    except Exception as e:
        logger.error(f"Error batch storing wallet tags: {e}", exc_info=True)
        return 0


def get_wallet_tags(
    wallet: Optional[str] = None,
    tag: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 100,
    db_path: str = _WALLET_TAGS_DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Retrieve wallet tags from the database.

    Args:
        wallet: Optional wallet address to filter by
        tag: Optional tag type to filter by
        min_confidence: Minimum confidence threshold (0.0 to 1.0)
        limit: Maximum number of tags to return
        db_path: Path to wallet tags database

    Returns:
        List of tag dictionaries
    """
    try:
        db = _get_db(db_path)
        _ensure_wallet_tags_table(db)

        # Build query
        where_clauses = []
        params = []

        if wallet:
            where_clauses.append("wallet = ?")
            params.append(wallet)

        if tag:
            where_clauses.append("tag = ?")
            params.append(tag)

        if min_confidence > 0.0:
            where_clauses.append("confidence >= ?")
            params.append(min_confidence)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        query = f"""
            SELECT id, wallet, tag, confidence, metadata, timestamp
            FROM wallet_tags
            WHERE {where_sql}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        rows = db.execute(query, params).fetchall()

        if not rows:
            return []

        # Column names
        columns = ["id", "wallet", "tag", "confidence", "metadata", "timestamp"]

        # Convert to dictionaries
        results = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            results.append(row_dict)

        return results

    except Exception as e:
        logger.error(f"Error retrieving wallet tags: {e}", exc_info=True)
        return []
